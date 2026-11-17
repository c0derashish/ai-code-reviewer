import time

from ai_engine.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_review_prompt
from ai_engine.providers import ProviderError
from ai_engine.response_parser import ParseError, clean_issues, extract_issues
from analyzer.languages import get_language_name
from analyzer.static.python_analyzer import split_lines

DEFAULT_MAX_FILES = 8
DEFAULT_TIME_BUDGET_SECONDS = 150
MAX_FILE_CHARS = 30_000
MAX_CONSECUTIVE_PROVIDER_ERRORS = 2

UNREADABLE_ANSWER = "The AI answer could not be read."
DISABLED_NOTE = (
    "AI review is switched off. Set VEDIX_AI_PROVIDER, VEDIX_AI_MODEL and "
    "VEDIX_AI_API_KEY to turn it on."
)


def _new_report(provider) -> dict:
    return {
        "status": "ok",  # ok, disabled, skipped or failed
        "provider": provider.name if provider else None,
        "model": provider.model if provider else None,
        "prompt_version": PROMPT_VERSION,
        "note": None,
        "files_reviewed": 0,
        "files_failed": 0,
        "files_skipped": [],
        "file_errors": [],
        "findings": [],
        "finding_count": 0,
        "dropped": {"bad_format": 0, "unverified_line": 0, "duplicate": 0, "too_many": 0},
    }


def _skip(report, file_path, reason):
    report["files_skipped"].append({"file_path": file_path, "reason": reason})


def _python_errors(code_file) -> list:
    """Errors (not warnings) found by the validator."""
    result = code_file.validation_result
    if not result or result["status"] != "invalid":
        return []
    return [error for error in result["errors"] if error["severity"] == "error"]


def _metrics_text(code_file):
    result = code_file.analysis_result
    if not result or result.get("status") != "analyzed":
        return None

    metrics = result["metrics"]
    highest = result["function_summary"]["max_complexity"]
    highest = highest if highest is not None else "none"
    return (
        f"{metrics['code_lines']} code lines, {metrics['functions']} functions, "
        f"highest function complexity {highest}, deepest nesting {metrics['max_nesting_depth']}."
    )


def _review_one_file(code_file, provider, existing_for_file):
    """Ask the AI about one file. Raises ProviderError or ParseError."""
    lines = split_lines(code_file.source_code)
    known = [
        (issue["line"], issue["title"], issue["category"])
        for issue in sorted(existing_for_file, key=lambda issue: issue["line"])
    ]
    prompt = build_review_prompt(
        code_file.file_path,
        get_language_name(code_file.language),
        lines,
        known,
        _python_errors(code_file),
        _metrics_text(code_file),
    )

    answer = provider.complete(SYSTEM_PROMPT, prompt)
    raw_issues = extract_issues(answer)
    return clean_issues(raw_issues, code_file.file_path, lines, existing_for_file)


def review_project(
    project,
    provider,
    existing_issues=None,
    max_files=DEFAULT_MAX_FILES,
    time_budget_seconds=DEFAULT_TIME_BUDGET_SECONDS,
) -> dict:
    """Review files with an AI model. One request per file.

    Run detect_project_languages, validate_project and analyze_project first.
    existing_issues: issues from our other checks. They go into the prompt and
    the AI is not allowed to repeat them.
    Returns a report. Use analyzer.findings.ai_to_issues(project, report) for the
    issues VEDIX shows. Never raises because of the AI service.
    """
    existing = existing_issues or []
    report = _new_report(provider)

    if provider is None:
        report["status"] = "disabled"
        report["note"] = DISABLED_NOTE
        return report

    # which files can be sent at all
    eligible = []
    for code_file in project.files:
        if code_file.language is None:
            _skip(report, code_file.file_path, "language not recognized")
        elif len(code_file.source_code) > MAX_FILE_CHARS:
            _skip(report, code_file.file_path, "file too large for AI review")
        else:
            eligible.append(code_file)

    by_path = {}
    for issue in existing:
        by_path.setdefault(issue["file_path"], []).append(issue)

    # files with errors first, then files with the most known issues
    eligible.sort(
        key=lambda f: (
            0 if _python_errors(f) else 1,
            -len(by_path.get(f.file_path, [])),
            f.file_path,
        )
    )
    chosen = eligible[:max_files]
    for code_file in eligible[max_files:]:
        _skip(report, code_file.file_path, "over the file limit")

    started = time.monotonic()
    errors_in_a_row = 0

    for index, code_file in enumerate(chosen):
        if errors_in_a_row >= MAX_CONSECUTIVE_PROVIDER_ERRORS:
            for rest in chosen[index:]:
                _skip(report, rest.file_path, "stopped after repeated errors")
            break
        if time.monotonic() - started >= time_budget_seconds:
            for rest in chosen[index:]:
                _skip(report, rest.file_path, "time budget used up")
            break

        try:
            findings, dropped = _review_one_file(
                code_file, provider, by_path.get(code_file.file_path, [])
            )
        except ProviderError as error:
            errors_in_a_row += 1
            report["files_failed"] += 1
            report["file_errors"].append({"file_path": code_file.file_path, "message": str(error)})
            continue
        except ParseError:
            errors_in_a_row = 0  # the service did answer
            report["files_failed"] += 1
            report["file_errors"].append(
                {"file_path": code_file.file_path, "message": UNREADABLE_ANSWER}
            )
            continue

        errors_in_a_row = 0
        report["files_reviewed"] += 1
        report["findings"].extend(findings)
        for key, count in dropped.items():
            report["dropped"][key] += count

    report["findings"].sort(key=lambda f: (f["file_path"], f["line"], f["category"]))
    report["finding_count"] = len(report["findings"])

    if report["files_reviewed"] == 0:
        if report["files_failed"] > 0:
            report["status"] = "failed"
            report["note"] = "The AI review failed. See file_errors."
        else:
            report["status"] = "skipped"
            report["note"] = "No files were reviewed."
    elif report["files_failed"] > 0:
        report["note"] = f"{report['files_failed']} file(s) could not be reviewed."

    return report