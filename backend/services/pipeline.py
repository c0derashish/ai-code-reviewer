from ai_engine.reviewer import DEFAULT_MAX_FILES, DEFAULT_TIME_BUDGET_SECONDS, review_project
from analyzer.findings import (
    ai_to_issues,
    duplication_to_issues,
    static_to_issues,
    tool_to_issues,
    validation_to_issues,
)
from analyzer.languages import detect_project_languages
from analyzer.static.duplication import find_duplicates
from analyzer.static.external_tools import run_external_tools
from analyzer.static.runner import analyze_project
from analyzer.validation import validate_project
from features.extractor import extract_project_features


def run_pipeline(
    project,
    ai_provider=None,
    thresholds=None,
    use_external_tools=True,
    ai_max_files=DEFAULT_MAX_FILES,
    ai_time_budget_seconds=DEFAULT_TIME_BUDGET_SECONDS,
) -> dict:
    """Run every step on a project and return everything in one dictionary.

    project:            from input_manager (from_uploads, from_local_folder, ...)
    ai_provider:        None = no AI review. Otherwise an object from ai_engine
    thresholds:         custom smell thresholds, or None for the defaults
    use_external_tools: False skips Ruff and Bandit (faster)

    A tool or AI failure never stops the pipeline. It is written in the reports.
    Raises ValueError only for a bad threshold name.
    """
    languages = detect_project_languages(project)
    validation = validate_project(project)
    analysis = analyze_project(project, thresholds)

    tool_reports = run_external_tools(project) if use_external_tools else None
    duplication = find_duplicates(project)

    issues = (
        validation_to_issues(project)
        + static_to_issues(project)
        + tool_to_issues(project)
        + duplication_to_issues(project, duplication)
    )

    ai_report = None
    if ai_provider is not None:
        # the AI is told what we already found, so it does not repeat it
        ai_report = review_project(
            project,
            ai_provider,
            issues,
            max_files=ai_max_files,
            time_budget_seconds=ai_time_budget_seconds,
        )
        issues = issues + ai_to_issues(project, ai_report)

    extraction = extract_project_features(project, tool_reports, duplication)

    return {
        "languages": languages,
        "validation": validation,
        "analysis": analysis,
        "tool_reports": tool_reports,
        "duplication": duplication,
        "ai_report": ai_report,
        "extraction": extraction,
        "issues": issues,
    }