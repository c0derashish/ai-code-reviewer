from analyzer.static.integrations.bandit_runner import run_bandit
from analyzer.static.integrations.ruff_runner import run_ruff


def _is_eligible(code_file) -> bool:
    """Only Python files that passed validation and static analysis."""
    result = code_file.analysis_result
    return (
        code_file.language == "python"
        and result is not None
        and result["status"] == "analyzed"
    )


def run_external_tools(project) -> dict:
    """Run Ruff and Bandit. Run analyze_project(project) first.

    Findings are saved in code_file.analysis_result["tool_findings"].
    Returns one report per tool: status, version, note, finding_count.
    Keep these reports. Without them nobody can tell "no findings" from
    "the tool did not run".
    """
    files = [code_file for code_file in project.files if _is_eligible(code_file)]

    for code_file in files:
        code_file.analysis_result["tool_findings"] = []  # start fresh on every run

    reports = {}
    for name, runner in (("ruff", run_ruff), ("bandit", run_bandit)):
        report, by_file = runner(files)
        reports[name] = report
        for code_file in files:
            found = by_file.get(code_file.file_path, [])
            code_file.analysis_result["tool_findings"].extend(found)

    for code_file in files:
        code_file.analysis_result["tool_findings"].sort(
            key=lambda finding: (
                finding["line"], finding["column"], finding["source"], finding["rule"]
            )
        )

    return reports