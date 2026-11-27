import hashlib
import json
from datetime import datetime, timedelta

import mongomock
import pytest
from bson import ObjectId

from analyzer.static.integrations import tool_runner
from api import runner
from app_db import analyses as store
from app_db.connection import ensure_indexes
from input_manager import from_uploads

UID = ObjectId()
OTHER = ObjectId()
FILES = {"bad.py": "def broken(:\n", "ok.py": "x = 1\n"}
NO_LICENCE = {"status": "none", "spdx_id": None, "name": None}
MIT = {"status": "found", "spdx_id": "MIT", "name": "MIT License"}
HISTORY_KEYS = {
    "id", "project_id", "project_name", "source", "repo_url", "created_at", "scope",
    "primary_language", "files", "files_analyzed", "loc", "issue_count", "rule_issue_count",
    "severity_counts", "storage", "storage_reason", "licence", "status",
}


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


@pytest.fixture
def db():
    database = mongomock.MongoClient().vedix
    ensure_indexes(database)
    return database


def analyse(files):
    project = from_uploads("demo", [(path, text.encode("utf-8")) for path, text in files.items()])
    return project, runner.analyze(project, "project", None, 8, 90)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repo(licence):
    return {"owner": "o", "repo": "r", "url": "https://github.com/o/r", "licence": licence}


def test_a_full_analysis_is_stored(db):
    project, outcome = analyse(FILES)
    when = datetime(2026, 11, 20, 10, 0, 0)

    analysis_id = store.save_analysis(db, UID, project, outcome, "project", "upload", now=when)

    projects = list(db["projects"].find())
    assert len(projects) == 1
    assert (projects[0]["key"], projects[0]["name"]) == ("upload:demo", "demo")
    assert (projects[0]["source"], projects[0]["storage"]) == ("upload", "full")
    assert projects[0]["user_id"] == UID
    assert str(projects[0]["last_analysis_id"]) == analysis_id

    document = db["analyses"].find_one()
    assert str(document["_id"]) == analysis_id
    assert document["user_id"] == UID
    assert document["project_id"] == projects[0]["_id"]
    assert document["created_at"] == when
    assert (document["files"], document["files_analyzed"], document["loc"]) == (2, 1, 1)
    assert document["primary_language"] == "python"
    assert document["language_lines"] == {"python": 2}
    assert document["severity_counts"] == {"critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0}
    assert (document["issue_count"], document["rule_issue_count"]) == (1, 1)
    assert document["storage"] == "full"
    assert document["summary"]["files"] == 2
    assert document["file_entries"] == [
        {"path": "bad.py", "sha256": sha("def broken(:\n"), "language": "python", "size": 13},
        {"path": "ok.py", "sha256": sha("x = 1\n"), "language": "python", "size": 6},
    ]

    issues = list(db["analysis_issues"].find())
    assert len(issues) == 1
    assert (issues[0]["issue_id"], issues[0]["title"], issues[0]["file_path"]) == (
        "validation-1", "Syntax error", "bad.py")
    assert (issues[0]["n"], issues[0]["user_id"], issues[0]["analysis_id"]) == (0, UID, document["_id"])

    bad_id, ok_id = f"{UID}:{sha('def broken(:' + chr(10))}", f"{UID}:{sha('x = 1' + chr(10))}"
    assert {blob["_id"]: blob["content"] for blob in db["blobs"].find()} == {
        bad_id: "def broken(:\n", ok_id: "x = 1\n"}


def test_a_second_analysis_of_the_same_project_adds_history_not_a_project(db):
    first = analyse(FILES)
    second = analyse({"bad.py": "def broken(:\n", "ok.py": "x = 2\n"})

    id_one = store.save_analysis(db, UID, *first[:1], first[1], "project", "upload",
                                 now=datetime(2026, 11, 20, 10, 0, 0))
    id_two = store.save_analysis(db, UID, second[0], second[1], "project", "upload",
                                 now=datetime(2026, 11, 21, 10, 0, 0))

    assert db["projects"].count_documents({}) == 1
    assert db["analyses"].count_documents({}) == 2
    assert db["blobs"].count_documents({}) == 3  # bad.py is stored once, ok.py in two versions
    assert str(db["projects"].find_one()["last_analysis_id"]) == id_two
    assert id_one != id_two


def test_a_repository_without_a_licence_is_stored_in_full(db):
    project, outcome = analyse(FILES)

    analysis_id = store.save_analysis(
        db, UID, project, outcome, "project", "github", repo(NO_LICENCE),
        now=datetime(2026, 11, 20, 10, 0, 0),
    )

    document = db["analyses"].find_one()
    assert str(document["_id"]) == analysis_id
    assert (document["source"], document["storage"]) == ("github", "full")
    assert document["repo_url"] == "https://github.com/o/r"
    assert document["licence"] == NO_LICENCE
    assert "No licence was found" in document["storage_reason"]
    assert document["file_entries"] == []
    assert (document["files"], document["loc"], document["issue_count"]) == (2, 1, 1)
    assert document["severity_counts"]["high"] == 1

    assert db["analysis_issues"].count_documents({}) == 0
    assert db["blobs"].count_documents({}) == 0
    saved_project = db["projects"].find_one()
    assert (saved_project["key"], saved_project["name"], saved_project["storage"]) == (
        "github:o/r", "o/r", "link_only")

    everything = json.dumps(
        [list(db[name].find()) for name in ("analyses", "projects", "analysis_issues", "blobs")],
        default=str,
    )
    for text in ("def broken", "x = 1", "Syntax error"):
        assert text not in everything

    document = db["analyses"].find_one({"_id": ObjectId(analysis_id)})
    assert store.get_files(db, UID, document) is None
    detail = store.history_detail(db, UID, document)
    assert (detail["issues"], detail["issues_stored"]) == ([], False)


def test_a_repository_with_an_open_licence_is_stored_in_full(db):
    project, outcome = analyse(FILES)

    store.save_analysis(db, UID, project, outcome, "project", "github", repo(MIT))

    document = db["analyses"].find_one()
    assert document["storage"] == "full"
    assert len(document["file_entries"]) == 2
    assert db["analysis_issues"].count_documents({}) == 1
    assert db["blobs"].count_documents({}) == 2
    assert db["projects"].find_one()["licence"] == MIT


def test_history_is_newest_first_and_private(db):
    project, outcome = analyse(FILES)
    base = datetime(2026, 11, 1, 9, 0, 0)
    ids = [
        store.save_analysis(db, UID, project, outcome, "project", "upload", now=base + timedelta(hours=n))
        for n in range(3)
    ]
    store.save_analysis(db, OTHER, project, outcome, "project", "upload", now=base)

    items = store.list_history(db, UID)

    assert [item["id"] for item in items] == ids[::-1]
    assert set(items[0]) == HISTORY_KEYS
    assert items[0]["created_at"] == "2026-11-01T11:00:00Z"
    assert (items[0]["project_name"], items[0]["storage"], items[0]["status"]) == ("demo", "full", "done")
    assert store.list_history(db, UID, limit=1, skip=1)[0]["id"] == ids[1]
    assert len(store.list_history(db, UID, limit=999)) == 3
    assert len(store.list_history(db, OTHER)) == 1
    assert store.list_history(db, ObjectId()) == []


def test_reading_one_analysis(db):
    project, outcome = analyse(FILES)
    analysis_id = store.save_analysis(db, UID, project, outcome, "project", "upload")

    document = store.get_analysis(db, UID, analysis_id)
    assert document is not None
    assert store.get_analysis(db, OTHER, analysis_id) is None  # someone else's
    assert store.get_analysis(db, UID, "nope") is None
    assert store.get_analysis(db, UID, str(ObjectId())) is None

    assert store.get_issues(db, UID, document) == outcome["issues"]  # the same issues, in the same order
    assert store.get_issues(db, OTHER, document) == []

    detail = store.history_detail(db, UID, document)
    assert detail["issues_stored"] is True
    assert [issue["title"] for issue in detail["issues"]] == ["Syntax error"]
    assert detail["summary"]["files"] == 2

    assert store.get_files(db, UID, document) == [
        {"path": "bad.py", "language": "python", "content": "def broken(:\n"},
        {"path": "ok.py", "language": "python", "content": "x = 1\n"},
    ]
    assert store.get_files(db, OTHER, document) == []  # the files belong to the owner


def test_deleting_an_analysis_cleans_up(db):
    first = analyse(FILES)
    second = analyse({"bad.py": "def broken(:\n", "ok.py": "x = 2\n"})
    id_one = store.save_analysis(db, UID, first[0], first[1], "project", "upload",
                                 now=datetime(2026, 11, 20, 10, 0, 0))
    id_two = store.save_analysis(db, UID, second[0], second[1], "project", "upload",
                                 now=datetime(2026, 11, 21, 10, 0, 0))

    # someone else cannot delete it
    store.delete_analysis(db, OTHER, store.get_analysis(db, UID, id_one))
    assert db["analyses"].count_documents({}) == 2

    store.delete_analysis(db, UID, store.get_analysis(db, UID, id_one))

    assert db["analyses"].count_documents({}) == 1
    assert db["analysis_issues"].count_documents({}) == 1  # only the second analysis keeps its issue
    assert db["blobs"].count_documents({}) == 2           # the old ok.py is gone. bad.py is still used
    assert str(db["projects"].find_one()["last_analysis_id"]) == id_two

    store.delete_analysis(db, UID, store.get_analysis(db, UID, id_two))

    for name in ("analyses", "analysis_issues", "blobs", "projects"):
        assert db[name].count_documents({}) == 0


def insert(db, user_id, project_id, name, when, loc, rule, total, analysed, severity, languages):
    counts = dict.fromkeys(store.SEVERITIES, 0)
    counts.update(severity)
    db["analyses"].insert_one({
        "_id": ObjectId(), "user_id": user_id, "project_id": project_id, "project_name": name,
        "created_at": when, "files_analyzed": analysed, "loc": loc, "issue_count": total,
        "rule_issue_count": rule, "severity_counts": counts, "language_lines": languages,
    })


def test_analytics(db):
    p1, p2, p3 = ObjectId(), ObjectId(), ObjectId()
    insert(db, UID, p1, "P1", datetime(2026, 10, 5, 9), 100, 10, 12, 4, {"high": 2, "medium": 4, "low": 6}, {"python": 150})
    insert(db, UID, p1, "P1", datetime(2026, 11, 5, 9), 200, 10, 11, 5, {"high": 1, "medium": 4, "low": 6}, {"python": 300})
    insert(db, UID, p2, "P2", datetime(2026, 11, 10, 9), 50, 5, 5, 2, {"low": 5}, {"python": 50, "javascript": 20})
    insert(db, UID, p3, "P3", datetime(2026, 11, 12, 9), 0, 0, 1, 0, {"info": 1}, {})
    insert(db, OTHER, ObjectId(), "Not mine", datetime(2026, 11, 12, 9), 999, 99, 99, 9, {"high": 99}, {"go": 999})

    result = store.analytics(db, UID)

    assert result == {
        "totals": {
            "projects": 3, "analyses": 4, "files_analyzed": 7, "loc": 250,
            "issue_count": 17, "rule_issue_count": 15, "issues_per_100_loc": 6.0,
        },
        "severity": {"critical": 0, "high": 1, "medium": 4, "low": 11, "info": 1},
        "languages": [{"language": "python", "lines": 350}, {"language": "javascript", "lines": 20}],
        "trend": [
            {"month": "2026-10", "analyses": 1, "issues_per_100_loc": 10.0},
            {"month": "2026-11", "analyses": 2, "issues_per_100_loc": 6.0},
        ],
        "projects": [
            {"project_id": str(p1), "project_name": "P1", "analyses": 2, "latest_at": "2026-11-05T09:00:00Z",
             "loc": 200, "latest_issue_count": 11, "latest_issues_per_100_loc": 5.0},
            {"project_id": str(p2), "project_name": "P2", "analyses": 1, "latest_at": "2026-11-10T09:00:00Z",
             "loc": 50, "latest_issue_count": 5, "latest_issues_per_100_loc": 10.0},
            {"project_id": str(p3), "project_name": "P3", "analyses": 1, "latest_at": "2026-11-12T09:00:00Z",
             "loc": 0, "latest_issue_count": 1, "latest_issues_per_100_loc": None},
        ],
        "truncated": False,
    }

    assert store.analytics(db, ObjectId()) == {
        "totals": {"projects": 0, "analyses": 0, "files_analyzed": 0, "loc": 0,
                   "issue_count": 0, "rule_issue_count": 0, "issues_per_100_loc": None},
        "severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "languages": [],
        "trend": [],
        "projects": [],
        "truncated": False,
    }