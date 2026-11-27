import logging

from analyzer.findings import SEVERITIES, STAGE_TEXT
from app_db import analyses as history_db
from services.pipeline import run_pipeline

log = logging.getLogger("vedix.api")

MAX_ISSUES = 2000
FAILED_MESSAGE = "The analysis failed because of a server problem."
SAVE_FAILED_MESSAGE = "The analysis could not be saved to your history."

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


def build_stats(result, issues) -> dict:
    """The numbers saved with an analysis. loc counts code lines of the analysed files only."""
    extraction = result["extraction"]
    counts = dict.fromkeys(SEVERITIES, 0)
    for issue in issues:
        if issue["severity"] in counts:
            counts[issue["severity"]] += 1

    return {
        "files": extraction["summary"]["files"],
        "files_analyzed": extraction["summary"]["analyzed"],
        "loc": sum(row["loc"] or 0 for row in extraction["rows"]),
        "primary_language": result["languages"]["primary_language"],
        "language_lines": {
            language: info["lines"] for language, info in result["languages"]["languages"].items()
        },
        "severity_counts": counts,
        "issue_count": len(issues),
        "rule_issue_count": sum(1 for issue in issues if issue["source"] != "ai"),
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
    issues = [issue_to_api(issue) for issue in issues[:MAX_ISSUES]]

    return {
        "issues": issues,
        "summary": build_summary(project, result, len(issues), truncated),
        "stats": build_stats(result, issues),
    }


def run_job(store, job_id, project, scope, ai_provider, ai_max_files, ai_time_budget, save=None):
    """Runs in a background thread. Never raises.

    save: None, or {"database", "user_id", "source", "repo"} to save the result for a signed-in user.
    """
    store.mark_running(job_id)
    try:
        outcome = analyze(project, scope, ai_provider, ai_max_files, ai_time_budget)
    except Exception:  # a crash must end as "failed", never as a job stuck on "running"
        log.exception("Analysis %s crashed.", job_id[:8])
        store.fail(job_id, FAILED_MESSAGE)
        return

    summary = outcome["summary"]
    if save is not None:
        try:
            summary["saved_analysis_id"] = history_db.save_analysis(
                save["database"], save["user_id"], project, outcome, scope, save["source"], save["repo"]
            )
            summary["saved"] = True
        except Exception:  # a failed save must not lose the result the user is waiting for
            log.exception("Saving analysis %s failed.", job_id[:8])
            summary["saved"] = False
            summary["save_error"] = SAVE_FAILED_MESSAGE

    store.finish(job_id, outcome["issues"], summary)