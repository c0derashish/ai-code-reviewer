import json
from collections import Counter

import pytest

from analyzer.static.integrations import tool_runner
from input_manager import from_uploads
from services.pipeline import run_pipeline

CODE = "\n".join([
    '"""Module doc."""',
    "",
    "class Calculator:",
    '    """A calculator."""',
    "",
    "    def add(self, a, b):",
    '        """Add two numbers."""',
    "        return a + b",
    "",
    "    def divide(self, a, b=1, *args, **kwargs):",
    "        if b == 0:",
    "            return None",
    "        return a / b",
    "",
    "",
    "def helper(x):",
    "    for i in x:",
    "        if i and i > 0:",
    "            print(i)",
    "",
])

LOW_LIMITS = {
    "long_method_lines": 3,
    "max_parameters": 1,
    "max_nesting_depth": 1,
    "max_complexity": 3,
    "large_class_lines": 10,
    "large_class_methods": 1,
}


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    """Pretend Ruff and Bandit are not installed, so tests give the same result everywhere."""
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def complete(self, system, user):
        self.calls.append(user)
        return self.answer(user)


def fake_answer(user):
    if "File: calc.py" in user:
        issue = {
            "line": 11, "code_quote": "if b == 0:", "severity": "medium",
            "category": "bug", "title": "Division check is incomplete",
            "explanation": "Only zero is handled.", "confidence": "high",
        }
        return json.dumps({"issues": [issue]})
    return '{"issues": []}'


def make_project():
    files = {"calc.py": CODE, "bad.py": "def broken(:\n"}
    return from_uploads("demo", [(path, text.encode("utf-8")) for path, text in files.items()])


def test_pipeline_runs_every_step():
    provider = FakeProvider(fake_answer)

    result = run_pipeline(make_project(), ai_provider=provider, thresholds=LOW_LIMITS)

    assert set(result) == {
        "languages", "validation", "analysis", "tool_reports",
        "duplication", "ai_report", "extraction", "issues",
    }
    assert result["languages"]["primary_language"] == "python"
    assert result["validation"] == {
        "files": 2, "valid": 1, "invalid": 1, "not_checked": 0, "errors": 1, "warnings": 0,
    }
    assert result["analysis"] == {"analyzed": 1, "not_analyzed": 1, "smells": 7}
    assert result["tool_reports"]["ruff"]["status"] == "unavailable"
    assert result["tool_reports"]["bandit"]["status"] == "unavailable"
    assert result["duplication"]["status"] == "ok"

    assert result["ai_report"]["status"] == "ok"
    assert result["ai_report"]["files_reviewed"] == 2
    assert result["ai_report"]["finding_count"] == 1
    assert len(provider.calls) == 2

    assert result["extraction"]["summary"] == {"files": 2, "analyzed": 1, "not_analyzed": 1}

    issues = result["issues"]
    sources = Counter(issue["id"].rsplit("-", 1)[0] for issue in issues)
    assert sources == {"validation": 1, "static": 7, "ai": 1}
    assert len({issue["id"] for issue in issues}) == 9


def test_pipeline_without_ai():
    result = run_pipeline(make_project(), thresholds=LOW_LIMITS)

    assert result["ai_report"] is None
    sources = Counter(issue["id"].rsplit("-", 1)[0] for issue in result["issues"])
    assert sources == {"validation": 1, "static": 7}


def test_pipeline_can_skip_the_tools():
    result = run_pipeline(make_project(), use_external_tools=False)

    assert result["tool_reports"] is None
    tools = result["extraction"]["run"]["tools"]
    assert tools["ruff"] == {"status": "not_run", "version": None}
    assert tools["bandit"] == {"status": "not_run", "version": None}
    assert result["extraction"]["rows"][1]["lint_violations"] is None