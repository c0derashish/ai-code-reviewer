import hashlib
import platform
import uuid
from datetime import datetime, timezone

from analyzer.static.runner import METRICS_VERSION
from features.schema import FEATURE_NAMES, SCHEMA_VERSION


def _is_analyzed(result) -> bool:
    return result is not None and result.get("status") == "analyzed"


def _missing_features() -> dict:
    return {name: None for name in FEATURE_NAMES}


def _tool_count(result, source, report):
    """How many findings a tool gave for one file.

    None (unknown) when the tool did not run or did not finish well.
    Writing 0 there would say "no problems", and we do not know that.
    """
    if report is None or report.get("status") != "ok":
        return None
    findings = result.get("tool_findings")
    if findings is None:
        return None
    return sum(1 for finding in findings if finding["source"] == source)


def _duplication_ratio(code_file, duplication_report):
    if duplication_report is None or duplication_report.get("status") != "ok":
        return None
    entry = duplication_report["files"].get(code_file.file_path)
    return entry["ratio"] if entry else None


def _features_of(code_file, tool_reports, duplication_report) -> dict:
    result = code_file.analysis_result
    metrics = result["metrics"]
    functions = result["function_summary"]
    reports = tool_reports or {}

    return {
        "loc": metrics["code_lines"],
        "blank_lines": metrics["blank_lines"],
        "comment_lines": metrics["comment_lines"],
        "functions": metrics["functions"],
        "classes": metrics["classes"],
        "imports": metrics["imports"],
        "variables": metrics["variables"],
        "avg_function_length": functions["average_length"],
        "max_function_length": functions["max_length"],
        "avg_cyclomatic_complexity": functions["average_complexity"],
        "max_cyclomatic_complexity": functions["max_complexity"],
        "max_nesting_depth": metrics["max_nesting_depth"],
        "documentation_coverage": result["documentation"]["coverage_percent"],
        "duplication_ratio": _duplication_ratio(code_file, duplication_report),
        "code_smells": len(result["smells"]),
        "lint_violations": _tool_count(result, "ruff", reports.get("ruff")),
        "security_findings": _tool_count(result, "bandit", reports.get("bandit")),
    }


def _note(result):
    if result is None:
        return "Static analysis was not run for this file."
    return result.get("note") or "This file was not analysed."


def _build_row(project, code_file, run_id, tool_reports, duplication_report) -> dict:
    result = code_file.analysis_result
    analyzed = _is_analyzed(result)

    row = {
        "run_id": run_id,
        "project_id": project.project_id,
        "project_name": project.project_name,
        "file_id": f"{project.project_id}/{code_file.file_path}",
        "file_path": code_file.file_path,
        "language": code_file.language,
        "content_sha256": hashlib.sha256(code_file.source_code.encode("utf-8")).hexdigest(),
        "analysis_status": "analyzed" if analyzed else "not_analyzed",
        "note": None if analyzed else _note(result),
    }

    if analyzed:
        row.update(_features_of(code_file, tool_reports, duplication_report))
    else:
        row.update(_missing_features())
    return row


def _tool_info(tool_reports, name) -> dict:
    report = (tool_reports or {}).get(name)
    if report is None:
        return {"status": "not_run", "version": None}
    return {"status": report["status"], "version": report["version"]}


def _duplication_info(report) -> dict:
    if report is None:
        return {"status": "not_run", "version": None, "settings": None}
    return {
        "status": report["status"],
        "version": report["version"],
        "settings": dict(report["settings"]),
    }


def _thresholds_used(project):
    """The smell thresholds used. All analysed files of a run share the same ones."""
    for code_file in project.files:
        if _is_analyzed(code_file.analysis_result):
            return dict(code_file.analysis_result["thresholds"])
    return None


def extract_project_features(
    project, tool_reports=None, duplication_report=None, run_id=None, analyzed_at=None
) -> dict:
    """Turn the analysis of a project into feature rows (one row per file).

    Run these first: detect_project_languages, validate_project, analyze_project.
    Optional: run_external_tools (pass its reports as tool_reports) and
    find_duplicates (pass its report as duplication_report).
    A tool that was not run gives missing (None) values, never 0.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    analyzed_at = analyzed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    rows = [
        _build_row(project, code_file, run_id, tool_reports, duplication_report)
        for code_file in project.files
    ]
    analyzed_count = sum(1 for row in rows if row["analysis_status"] == "analyzed")

    return {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": run_id,
            "analyzed_at": analyzed_at,  # UTC
            "schema_version": SCHEMA_VERSION,
            "metrics_version": METRICS_VERSION,
            "python_version": platform.python_version(),
            "thresholds": _thresholds_used(project),
            "tools": {
                "ruff": _tool_info(tool_reports, "ruff"),
                "bandit": _tool_info(tool_reports, "bandit"),
            },
            "duplication": _duplication_info(duplication_report),
        },
        "summary": {
            "files": len(rows),
            "analyzed": analyzed_count,
            "not_analyzed": len(rows) - analyzed_count,
        },
        "rows": rows,
    }