import json

from analyzer.static.integrations.tool_runner import (
    ToolError,
    base_name,
    python_command,
    run_tool,
)

# Only the "F" rules (Pyflakes): unused imports and variables, undefined names, and similar.
RUFF_RULES = "F"


def build_ruff_command(file_names):
    return python_command("ruff") + [
        "check",
        "--isolated",   # ignore every config file
        "--no-cache",
        "--exit-zero",  # exit code 0 even when problems are found
        "--select", RUFF_RULES,
        "--output-format", "json",
    ] + file_names


def _convert(item, names):
    """One Ruff result -> our finding. Returns None if we should ignore it."""
    if not isinstance(item, dict):
        return None

    code = item.get("code")
    if not code:
        return None  # a syntax error. The validator (Phase 3) already reports those

    file_path = names.get(base_name(item.get("filename", "")))
    if file_path is None:
        return None

    # Files were written under safe names, so the REAL name is checked here.
    # In __init__.py an "unused" import is often meant to be re-exported.
    if code == "F401" and base_name(file_path) == "__init__.py":
        return None

    location = item.get("location")
    if not isinstance(location, dict):
        return None
    line = location.get("row")
    column = location.get("column")
    if not isinstance(line, int) or not isinstance(column, int):
        return None

    return {
        "file_path": file_path,
        "source": "ruff",
        "rule": str(code),
        "line": line,
        "column": column,
        "message": str(item.get("message", ""))[:300],
    }


def parse_ruff_output(exit_code, stdout, stderr, names):
    if exit_code != 0:
        raise ToolError(f"exit code {exit_code}")

    text = stdout.decode("utf-8", errors="replace").strip()
    if text == "":
        return []

    try:
        data = json.loads(text)
    except ValueError:
        raise ToolError("the answer could not be read") from None
    if not isinstance(data, list):
        raise ToolError("the answer has an unexpected shape")

    findings = []
    for item in data:
        finding = _convert(item, names)
        if finding is not None:
            findings.append(finding)
    return findings


def run_ruff(code_files):
    return run_tool("ruff", build_ruff_command, parse_ruff_output, code_files)