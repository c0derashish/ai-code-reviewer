import logging

from analyzer.findings import STAGE_TEXT
from services.pipeline import run_pipeline

log = logging.getLogger("vedix.api")

MAX_ISSUES = 2000
FAILED_MESSAGE = "The analysis failed because of a server problem."

# The title of the warning "this import points inside the project but finds nothing".
DEPENDENCY_TITLE = STAGE_TEXT["dependency"][2]


def _clip(value, limit):
    return value[:limit] if isinstance(value, str) else None


def issue_to_api(issue) -> dict:
    """Only the fields of the contract, plus source and rule. Text is cut to the sizes VEDIX accepts."""
    source = issue.get("source") or issue["id"].rsplit("-", 1)[0]  # "validation-3" -> "validation"
    return {
        "id": str(issue["id"])[:60],
        "file_path": issue["file_path"],
        "line": int(issue["line"]),
        "severity": issue["severity"],
        "category": issue["category"],
        "title": str(issue["title"])[:200],
        "explanation": str(issue["explanation"])[:2000],
        "suggestion": _clip(issue.get("suggestion"), 2000) or None,
        "before": _clip(issue.get("before"), 4000),
        "after": _clip(issue.get("after"), 4000),
        "source": _clip(source, 40),
        "rule": _clip(issue.get("rule"), 80),
    }


def build_summary(project, result, issue_count, truncated) -> dict:
    extraction = result["extraction"]["summary"]
    tools = result["tool_reports"] or {}
    ai_report = result["ai_report"]

    return {
        "files": extraction["files"],
        "analyzed": extraction["analyzed"],
        "not_analyzed": extraction["not_analyzed"],
        "files_skipped": project.skipped_count,
        "primary_language": result["languages"]["primary_language"],
        "issue_count": issue_count,
        "issues_truncated": truncated,
        "tools": {name: report["status"] for name, report in tools.items()},
        "duplication": result["duplication"]["status"],
        "ai": ai_report["status"] if ai_report else "not_used",
    }


def analyze(project, scope, ai_provider, ai_max_files, ai_time_budget) -> dict:
    result = run_pipeline(
        project,
        ai_provider=ai_provider,
        ai_max_files=ai_max_files,
        ai_time_budget_seconds=ai_time_budget,
    )

    issues = result["issues"]
    if scope == "file":
        # one file alone cannot see its sibling files, so these warnings would be wrong
        issues = [issue for issue in issues if issue["title"] != DEPENDENCY_TITLE]

    truncated = len(issues) > MAX_ISSUES
    issues = issues[:MAX_ISSUES]

    return {
        "issues": [issue_to_api(issue) for issue in issues],
        "summary": build_summary(project, result, len(issues), truncated),
    }


def run_job(store, job_id, project, scope, ai_provider, ai_max_files, ai_time_budget):
    """Runs in a background thread. Never raises."""
    store.mark_running(job_id)
    try:
        outcome = analyze(project, scope, ai_provider, ai_max_files, ai_time_budget)
    except Exception:  # a crash must end as "failed", never as a job stuck on "running"
        log.exception("Analysis %s crashed.", job_id[:8])
        store.fail(job_id, FAILED_MESSAGE)
        return
    store.finish(job_id, outcome["issues"], outcome["summary"])