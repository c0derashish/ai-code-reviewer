import hashlib

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

from app_db.clock import utc_now
from app_db.licences import describe_storage

SEVERITIES = ("critical", "high", "medium", "low", "info")
MAX_LIMIT = 200
ANALYTICS_LIMIT = 1000  # the most recent analyses used for the charts

ISSUE_FIELDS = (
    "file_path", "line", "severity", "category", "title", "explanation",
    "suggestion", "before", "after", "source", "rule",
)


def _iso(value) -> str:
    return value.isoformat(timespec="seconds") + "Z"  # stored times are UTC


def _sha(text) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _object_id(text):
    if isinstance(text, str) and ObjectId.is_valid(text):
        return ObjectId(text)
    return None


def project_key(source, name, repo) -> str:
    """What makes two analyses belong to the same project (for one user)."""
    if source == "github":
        return f"github:{repo['owner']}/{repo['repo']}".lower()
    return f"upload:{name.strip().lower()}"


# ---------- saving ----------

def _upsert_project(db, user_id, key, fields, now):
    update = {"$set": {**fields, "updated_at": now}, "$setOnInsert": {"created_at": now}}
    for attempt in range(2):  # two requests can race to create the same project
        try:
            return db["projects"].find_one_and_update(
                {"user_id": user_id, "key": key}, update,
                upsert=True, return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            if attempt == 1:
                raise


def _store_blobs(db, user_id, project, entries, now):
    """Save the text of each file once per user. A file that is already saved is left alone."""
    ids = [f"{user_id}:{entry['sha256']}" for entry in entries]
    known = {blob["_id"] for blob in db["blobs"].find({"_id": {"$in": ids}}, {"_id": 1})}

    new = {}  # a dictionary, so the same text twice in one project is added once
    for code_file, entry, blob_id in zip(project.files, entries, ids):
        if blob_id not in known and blob_id not in new:
            new[blob_id] = {
                "_id": blob_id,
                "user_id": user_id,
                "sha256": entry["sha256"],
                "content": code_file.source_code,
                "size": entry["size"],
                "created_at": now,
            }
    if not new:
        return

    try:
        db["blobs"].insert_many(list(new.values()), ordered=False)
    except BulkWriteError as error:
        # another request saved the same text at the same moment. That is fine
        details = getattr(error, "details", None) or {}
        if any(item.get("code") != 11000 for item in details.get("writeErrors", [])):
            raise


def _store_issues(db, user_id, analysis_id, issues):
    documents = []
    for position, issue in enumerate(issues):
        document = {name: issue.get(name) for name in ISSUE_FIELDS}
        document.update(
            {"issue_id": issue["id"], "user_id": user_id, "analysis_id": analysis_id, "n": position}
        )
        documents.append(document)
    if documents:
        db["analysis_issues"].insert_many(documents, ordered=False)


def save_analysis(db, user_id, project, outcome, scope, source, repo=None, now=None) -> str:
    """Save one finished analysis. Returns its id (text).

    outcome: what api.runner.analyze returned (issues, summary, stats).
    source: "upload" or "github". repo: {"owner", "repo", "url", "licence"} for GitHub.
    A GitHub repository without a clearly open licence is stored as a link and counts only.
    """
    now = now or utc_now()
    decision = describe_storage(source, repo["licence"] if repo else None)
    full = decision["storage"] == "full"
    name = f"{repo['owner']}/{repo['repo']}" if repo else project.project_name

    project_doc = _upsert_project(
        db, user_id, project_key(source, name, repo),
        {
            "user_id": user_id, "name": name, "source": source,
            "repo_url": repo["url"] if repo else None,
            "licence": repo["licence"] if repo else None,
            "storage": decision["storage"],
        },
        now,
    )

    analysis_id = ObjectId()
    entries = []
    if full:
        entries = [
            {
                "path": code_file.file_path,
                "sha256": _sha(code_file.source_code),
                "language": code_file.language or "plaintext",
                "size": code_file.size_bytes,
            }
            for code_file in project.files
        ]
        _store_blobs(db, user_id, project, entries, now)
        _store_issues(db, user_id, analysis_id, outcome["issues"])

    stats = outcome["stats"]
    analysis = {
        "_id": analysis_id,
        "user_id": user_id,
        "project_id": project_doc["_id"],
        "project_name": name,
        "created_at": now,
        "scope": scope,
        "source": source,
        "repo_url": repo["url"] if repo else None,
        "licence": repo["licence"] if repo else None,
        "storage": decision["storage"],
        "storage_reason": decision["reason"],
        "files": stats["files"],
        "files_analyzed": stats["files_analyzed"],
        "loc": stats["loc"],
        "primary_language": stats["primary_language"],
        "language_lines": stats["language_lines"],
        "severity_counts": stats["severity_counts"],
        "issue_count": stats["issue_count"],
        "rule_issue_count": stats["rule_issue_count"],
        "file_entries": entries,
        "summary": outcome["summary"],
    }

    # The analysis document goes in last, so the history never shows a half-saved analysis.
    try:
        db["analyses"].insert_one(analysis)
    except PyMongoError:
        if full:
            db["analysis_issues"].delete_many({"analysis_id": analysis_id})
        raise

    db["projects"].update_one({"_id": project_doc["_id"]}, {"$set": {"last_analysis_id": analysis_id}})
    return str(analysis_id)


# ---------- reading ----------

def history_item(document) -> dict:
    return {
        "id": str(document["_id"]),
        "project_id": str(document["project_id"]),
        "project_name": document["project_name"],
        "source": document["source"],
        "repo_url": document.get("repo_url"),
        "created_at": _iso(document["created_at"]),
        "scope": document["scope"],
        "primary_language": document.get("primary_language"),
        "files": document["files"],
        "files_analyzed": document["files_analyzed"],
        "loc": document["loc"],
        "issue_count": document["issue_count"],
        "rule_issue_count": document["rule_issue_count"],
        "severity_counts": document["severity_counts"],
        "storage": document["storage"],
        "storage_reason": document.get("storage_reason"),
        "licence": document.get("licence"),
        "status": "done",
    }


def list_history(db, user_id, limit=50, skip=0) -> list:
    limit = max(1, min(int(limit), MAX_LIMIT))
    skip = max(0, int(skip))
    cursor = (
        db["analyses"]
        .find({"user_id": user_id}, {"file_entries": 0, "summary": 0})
        .sort([("created_at", -1), ("_id", -1)])
        .skip(skip)
        .limit(limit)
    )
    return [history_item(document) for document in cursor]


def get_analysis(db, user_id, analysis_id):
    """The analysis document of this user, or None (unknown, not valid, or someone else's)."""
    object_id = _object_id(analysis_id)
    if object_id is None:
        return None
    return db["analyses"].find_one({"_id": object_id, "user_id": user_id})


def get_issues(db, user_id, document) -> list:
    cursor = db["analysis_issues"].find(
        {"analysis_id": document["_id"], "user_id": user_id}
    ).sort("n", 1)

    issues = []
    for stored in cursor:
        issue = {name: stored.get(name) for name in ISSUE_FIELDS}
        issue["id"] = stored["issue_id"]
        issues.append(issue)
    return issues


def history_detail(db, user_id, document) -> dict:
    item = history_item(document)
    stored = document["storage"] == "full"
    item["issues"] = get_issues(db, user_id, document) if stored else []
    item["issues_stored"] = stored
    item["summary"] = document.get("summary")
    return item


def get_files(db, user_id, document):
    """The saved files, or None when only the link was stored."""
    if document["storage"] != "full":
        return None

    entries = document.get("file_entries", [])
    blob_ids = [f"{user_id}:{entry['sha256']}" for entry in entries]
    contents = {
        blob["_id"]: blob["content"]
        for blob in db["blobs"].find({"_id": {"$in": blob_ids}, "user_id": user_id})
    }
    return [
        {"path": entry["path"], "language": entry["language"], "content": contents[blob_id]}
        for entry, blob_id in zip(entries, blob_ids)
        if blob_id in contents
    ]


# ---------- deleting ----------

def _remove_unused_blobs(db, user_id, document):
    gone = {entry["sha256"] for entry in document.get("file_entries", [])}
    if not gone:
        return

    for other in db["analyses"].find({"user_id": user_id}, {"file_entries": 1}):
        for entry in other.get("file_entries", []):
            gone.discard(entry["sha256"])  # another analysis still uses this text

    if gone:
        db["blobs"].delete_many({"_id": {"$in": [f"{user_id}:{sha}" for sha in gone]}, "user_id": user_id})


def _refresh_project(db, user_id, project_id):
    latest = db["analyses"].find_one(
        {"user_id": user_id, "project_id": project_id}, sort=[("created_at", -1), ("_id", -1)]
    )
    if latest is None:
        db["projects"].delete_one({"_id": project_id, "user_id": user_id})
    else:
        db["projects"].update_one(
            {"_id": project_id, "user_id": user_id}, {"$set": {"last_analysis_id": latest["_id"]}}
        )


def delete_analysis(db, user_id, document):
    """Delete one analysis, its issues, and any file text no other analysis uses."""
    db["analysis_issues"].delete_many({"analysis_id": document["_id"], "user_id": user_id})
    db["analyses"].delete_one({"_id": document["_id"], "user_id": user_id})
    _remove_unused_blobs(db, user_id, document)
    _refresh_project(db, user_id, document["project_id"])


# ---------- analytics ----------

def _density(issues, loc):
    return round(issues / loc * 100, 2) if loc else None


def analytics(db, user_id) -> dict:
    """Numbers for the charts. There is no quality score, so the measure is issues per 100 code lines,
    counting only rule-based findings (AI findings change from run to run).

    totals, severity, languages and projects use the LATEST analysis of each project.
    The trend uses all analyses, grouped by month, and leaves out analyses with no code lines.
    """
    documents = list(
        db["analyses"]
        .find({"user_id": user_id}, {"file_entries": 0, "summary": 0})
        .sort([("created_at", -1), ("_id", -1)])
        .limit(ANALYTICS_LIMIT)
    )

    latest = {}
    counts = {}
    for document in documents:  # newest first, so the first one seen is the latest
        latest.setdefault(document["project_id"], document)
        counts[document["project_id"]] = counts.get(document["project_id"], 0) + 1

    loc = sum(d["loc"] for d in latest.values())
    rule_issues = sum(d["rule_issue_count"] for d in latest.values())

    severity = dict.fromkeys(SEVERITIES, 0)
    language_lines = {}
    for document in latest.values():
        for name in SEVERITIES:
            severity[name] += document["severity_counts"].get(name, 0)
        for language, lines in document["language_lines"].items():
            language_lines[language] = language_lines.get(language, 0) + lines

    months = {}
    for document in documents:
        if document["loc"] <= 0:
            continue
        month = months.setdefault(document["created_at"].strftime("%Y-%m"), {"analyses": 0, "issues": 0, "loc": 0})
        month["analyses"] += 1
        month["issues"] += document["rule_issue_count"]
        month["loc"] += document["loc"]

    projects = [
        {
            "project_id": str(project_id),
            "project_name": document["project_name"],
            "analyses": counts[project_id],
            "latest_at": _iso(document["created_at"]),
            "loc": document["loc"],
            "latest_issue_count": document["issue_count"],
            "latest_issues_per_100_loc": _density(document["rule_issue_count"], document["loc"]),
        }
        for project_id, document in latest.items()
    ]
    projects.sort(key=lambda item: item["project_name"].lower())

    return {
        "totals": {
            "projects": len(latest),
            "analyses": len(documents),
            "files_analyzed": sum(d["files_analyzed"] for d in latest.values()),
            "loc": loc,
            "issue_count": sum(d["issue_count"] for d in latest.values()),
            "rule_issue_count": rule_issues,
            "issues_per_100_loc": _density(rule_issues, loc),
        },
        "severity": severity,
        "languages": [
            {"language": language, "lines": lines}
            for language, lines in sorted(language_lines.items(), key=lambda pair: (-pair[1], pair[0]))
        ],
        "trend": [
            {"month": name, "analyses": data["analyses"], "issues_per_100_loc": _density(data["issues"], data["loc"])}
            for name, data in sorted(months.items())
        ],
        "projects": projects,
        "truncated": len(documents) >= ANALYTICS_LIMIT,
    }