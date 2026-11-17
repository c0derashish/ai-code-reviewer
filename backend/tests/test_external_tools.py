import json
import re

import pytest

from analyzer.findings import CATEGORIES, SEVERITIES, tool_to_issues
from analyzer.languages import detect_project_languages
from analyzer.static.external_tools import run_external_tools
from analyzer.static.integrations import tool_runner
from analyzer.static.integrations.bandit_runner import parse_bandit_output
from analyzer.static.integrations.ruff_runner import parse_ruff_output
from analyzer.static.integrations.tool_runner import ToolError
from analyzer.static.runner import analyze_project
from analyzer.validation import validate_project
from input_manager import from_uploads

needs_ruff = pytest.mark.skipif(
    tool_runner.get_tool_version("ruff") is None, reason="ruff is not installed"
)
needs_bandit = pytest.mark.skipif(
    tool_runner.get_tool_version("bandit") is None, reason="bandit is not installed"
)


def make_project(files):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    validate_project(project)
    analyze_project(project)
    return project


def findings_of(project, path):
    return project.get_file(path).analysis_result["tool_findings"]


def pretend_tools_are_installed(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: "0.0.0")


# ---------- reading tool answers (no tool needed) ----------

def test_ruff_parser_reads_a_sample_answer():
    names = {"f0001.py": "a.py", "f0002.py": "pkg/__init__.py"}
    sample = [
        {"code": "F401", "message": "`os` imported but unused",
         "filename": "/tmp/vedix_x/f0001.py", "location": {"row": 1, "column": 8}},
        {"code": None, "message": "SyntaxError: something",
         "filename": "/tmp/vedix_x/f0001.py", "location": {"row": 2, "column": 1}},
        {"code": "F401", "message": "`os` imported but unused",
         "filename": "C:\\Temp\\vedix_x\\f0002.py", "location": {"row": 1, "column": 8}},
        {"code": "F821", "message": "Undefined name `y`",
         "filename": "C:\\Temp\\vedix_x\\f0001.py", "location": {"row": 3, "column": 5}},
        {"code": "F841", "message": "unknown file",
         "filename": "/tmp/other/f9999.py", "location": {"row": 1, "column": 1}},
    ]

    findings = parse_ruff_output(0, json.dumps(sample).encode("utf-8"), b"", names)

    assert findings == [
        {"file_path": "a.py", "source": "ruff", "rule": "F401", "line": 1, "column": 8,
         "message": "`os` imported but unused"},
        {"file_path": "a.py", "source": "ruff", "rule": "F821", "line": 3, "column": 5,
         "message": "Undefined name `y`"},
    ]


def test_ruff_parser_rejects_bad_answers():
    for exit_code, answer in [(2, b"[]"), (0, b"not json"), (0, b'{"a": 1}')]:
        with pytest.raises(ToolError):
            parse_ruff_output(exit_code, answer, b"", {})


def test_bandit_parser_reads_a_sample_answer():
    names = {"f0001.py": "a.py"}
    sample = {
        "errors": [],
        "results": [{
            "filename": "./f0001.py", "line_number": 1, "col_offset": 0,
            "test_id": "B307", "test_name": "blacklist",
            "issue_text": "Use of possibly insecure function - consider using safer ast.literal_eval.",
            "issue_severity": "MEDIUM", "issue_confidence": "HIGH",
            "issue_cwe": {"id": 78, "link": "https://cwe.mitre.org/data/definitions/78.html"},
        }],
    }
    answer = b"some log line\n" + json.dumps(sample).encode("utf-8")

    findings = parse_bandit_output(0, answer, b"", names)

    assert findings == [{
        "file_path": "a.py", "source": "bandit", "rule": "B307", "name": "blacklist",
        "line": 1, "column": 1,
        "message": "Use of possibly insecure function - consider using safer ast.literal_eval.",
        "severity": "MEDIUM", "confidence": "HIGH", "cwe": 78,
    }]
    assert parse_bandit_output(0, b'{"results": []}', b"", names) == []


def test_bandit_parser_rejects_bad_answers():
    cases = [(3, b'{"results": []}'), (0, b"nothing here"), (0, b'{"errors": []}')]
    for exit_code, answer in cases:
        with pytest.raises(ToolError):
            parse_bandit_output(exit_code, answer, b"", {})


# ---------- a broken tool must not break the review (no tool needed) ----------

def test_missing_tools_do_not_crash(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)
    project = make_project({"a.py": "x = 1\n"})

    reports = run_external_tools(project)

    assert reports["ruff"]["status"] == "unavailable"
    assert reports["bandit"]["status"] == "unavailable"
    assert "pip install ruff" in reports["ruff"]["note"]
    assert findings_of(project, "a.py") == []


def test_tool_failure_is_reported(monkeypatch):
    pretend_tools_are_installed(monkeypatch)
    monkeypatch.setattr(tool_runner, "run_command", lambda args, folder: (2, b"", b"boom"))
    project = make_project({"a.py": "x = 1\n"})

    reports = run_external_tools(project)

    for name in ("ruff", "bandit"):
        assert reports[name]["status"] == "failed"
        assert "exit code 2" in reports[name]["note"]
        assert reports[name]["detail"] == "boom"
    assert findings_of(project, "a.py") == []


def test_timeout_is_reported(monkeypatch):
    pretend_tools_are_installed(monkeypatch)

    def too_slow(args, folder):
        raise ToolError("timed out after 60 seconds")

    monkeypatch.setattr(tool_runner, "run_command", too_slow)
    project = make_project({"a.py": "x = 1\n"})

    reports = run_external_tools(project)

    assert reports["ruff"]["status"] == "failed"
    assert "timed out" in reports["ruff"]["note"]


def test_only_valid_python_files_are_sent(monkeypatch):
    pretend_tools_are_installed(monkeypatch)
    sent = []

    def fake_run(args, folder):
        sent.append([arg for arg in args if re.fullmatch(r"f\d{4}\.py", arg)])
        if "ruff" in args:
            return 0, b"[]", b""
        return 0, b'{"results": []}', b""

    monkeypatch.setattr(tool_runner, "run_command", fake_run)
    project = make_project({
        "good.py": "x = 1\n",
        "bad.py": "def broken(:\n",
        "a.js": "var a = 1;\n",
    })

    reports = run_external_tools(project)

    assert sent == [["f0001.py"], ["f0001.py"]]  # one file, to each tool
    assert reports["ruff"]["status"] == "ok"
    assert reports["bandit"]["status"] == "ok"


# ---------- issues for VEDIX (no tool needed) ----------

def test_tool_findings_become_vedix_issues():
    project = make_project({"a.py": "import os\nx = 1\ny = undefined_name\n"})
    project.get_file("a.py").analysis_result["tool_findings"] = [
        {"file_path": "a.py", "source": "ruff", "rule": "F401", "line": 1, "column": 8,
         "message": "`os` imported but unused"},
        {"file_path": "a.py", "source": "ruff", "rule": "F821", "line": 3, "column": 5,
         "message": "Undefined name `undefined_name`"},
        {"file_path": "a.py", "source": "ruff", "rule": "F999", "line": 2, "column": 1,
         "message": "Something odd"},
        {"file_path": "a.py", "source": "bandit", "rule": "B307", "name": "blacklist",
         "line": 99, "column": 1, "message": "Use of eval.", "severity": "HIGH",
         "confidence": "MEDIUM", "cwe": 78},
    ]

    issues = tool_to_issues(project)
    assert len(issues) == 4

    unused, undefined, other, security = issues

    assert unused["severity"] == "low"
    assert unused["category"] == "maintainability"
    assert unused["title"] == "Unused import"
    assert unused["line"] == 1
    assert unused["before"] == "import os"
    assert unused["source"] == "ruff"
    assert unused["rule"] == "F401"
    assert unused["explanation"].startswith("`os` imported but unused")

    assert undefined["severity"] == "high"
    assert undefined["category"] == "bug"
    assert undefined["line"] == 3

    assert other["title"] == "Ruff F999"
    assert other["severity"] == "low"
    assert other["category"] == "code_smell"

    assert security["severity"] == "high"
    assert security["category"] == "security"
    assert security["title"] == "Blacklist (B307)"
    assert security["line"] == 3  # line 99 does not exist, so it is moved inside the file
    assert security["before"] == "y = undefined_name"
    assert security["source"] == "bandit"
    assert "CWE-78" in security["explanation"]
    assert "confidence: medium" in security["explanation"]
    assert "not a confirmed vulnerability" in security["explanation"]

    assert len({issue["id"] for issue in issues}) == 4
    for issue in issues:
        assert issue["severity"] in SEVERITIES
        assert issue["category"] in CATEGORIES


# ---------- the real tools (skipped when not installed) ----------

@needs_ruff
def test_real_ruff_finds_an_unused_import():
    project = make_project({"a.py": "import os\n"})
    reports = run_external_tools(project)

    assert reports["ruff"]["status"] == "ok"
    assert any(f["rule"] == "F401" and f["line"] == 1 for f in findings_of(project, "a.py"))


@needs_ruff
def test_real_ruff_allows_unused_import_in_init_file():
    project = make_project({"pkg/__init__.py": "import os\n", "pkg/a.py": "import os\n"})
    reports = run_external_tools(project)

    assert reports["ruff"]["status"] == "ok"
    assert findings_of(project, "pkg/__init__.py") == []
    assert any(f["rule"] == "F401" for f in findings_of(project, "pkg/a.py"))


@needs_bandit
def test_real_bandit_finds_eval():
    project = make_project({"a.py": "x = eval('1 + 1')\n"})
    reports = run_external_tools(project)

    assert reports["bandit"]["status"] == "ok"
    assert any(f["source"] == "bandit" and f["line"] == 1 for f in findings_of(project, "a.py"))


@needs_bandit
def test_real_bandit_skips_assert():
    project = make_project({"a.py": "assert 1 == 1\n"})
    reports = run_external_tools(project)

    assert reports["bandit"]["status"] == "ok"
    assert findings_of(project, "a.py") == []


@needs_ruff
@needs_bandit
def test_real_tools_find_nothing_in_clean_code():
    project = make_project({"a.py": "x = 1\nprint(x)\n"})
    reports = run_external_tools(project)

    assert reports["ruff"]["status"] == "ok"
    assert reports["bandit"]["status"] == "ok"
    assert reports["ruff"]["finding_count"] == 0
    assert reports["bandit"]["finding_count"] == 0
    assert findings_of(project, "a.py") == []