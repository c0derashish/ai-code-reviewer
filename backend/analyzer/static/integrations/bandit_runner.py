import json

from analyzer.static.integrations.tool_runner import (
    ToolError,
    base_name,
    python_command,
    run_tool,
)

# B101 (assert used) is skipped. It flags every assert, mostly in tests,
# and is not a real security risk in this setting.
BANDIT_SKIPPED_TESTS = "B101"


def build_bandit_command(file_names):
    return python_command("bandit") + [
        "--format", "json",
        "--exit-zero",  # exit code 0 even when problems are found
        "--skip", BANDIT_SKIPPED_TESTS,
    ] + file_names


def _convert(item, names):
    """One Bandit result -> our finding. Returns None if we should ignore it."""
    if not isinstance(item, dict):
        return None

    file_path = names.get(base_name(item.get("filename", "")))
    line = item.get("line_number")
    if file_path is None or not isinstance(line, int):
        return None

    # Bandit counts columns from 0. We count from 1, like the editor.
    offset = item.get("col_offset")
    column = offset + 1 if isinstance(offset, int) and offset >= 0 else 1

    cwe = item.get("issue_cwe")
    cwe_id = cwe.get("id") if isinstance(cwe, dict) else None

    return {
        "file_path": file_path,
        "source": "bandit",
        "rule": str(item.get("test_id", "")),
        "name": str(item.get("test_name", "")),
        "line": line,
        "column": column,
        "message": str(item.get("issue_text", ""))[:300],
        "severity": str(item.get("issue_severity", "")).upper(),
        "confidence": str(item.get("issue_confidence", "")).upper(),
        "cwe": cwe_id if isinstance(cwe_id, int) else None,
    }


def parse_bandit_output(exit_code, stdout, stderr, names):
    if exit_code != 0:
        raise ToolError(f"exit code {exit_code}")

    text = stdout.decode("utf-8", errors="replace")
    start = text.find("{")
    if start == -1:
        raise ToolError("the answer could not be read")

    try:
        # raw_decode reads one JSON object and ignores any text after it
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        raise ToolError("the answer could not be read") from None

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise ToolError("the answer has an unexpected shape")

    findings = []
    for item in results:
        finding = _convert(item, names)
        if finding is not None:
            findings.append(finding)
    return findings


def run_bandit(code_files):
    return run_tool("bandit", build_bandit_command, parse_bandit_output, code_files)