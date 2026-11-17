import pytest

from analyzer.evaluation import radon_comparison
from analyzer.evaluation.radon_comparison import (
    compare_project,
    pair_functions,
    summarize_pairs,
)
from analyzer.languages import detect_project_languages
from analyzer.static.integrations import tool_runner
from analyzer.static.runner import analyze_project
from analyzer.validation import validate_project
from input_manager import from_uploads

needs_radon = pytest.mark.skipif(
    tool_runner.get_tool_version("radon") is None, reason="radon is not installed"
)


def make_project(files):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    validate_project(project)
    analyze_project(project)
    return project


def test_summary_of_pairs():
    pairs = [
        {"ours": 2, "radon": 2},
        {"ours": 3, "radon": 4},
        {"ours": 5, "radon": 3},
        {"ours": 1, "radon": 1},
    ]
    assert summarize_pairs(pairs) == {
        "count": 4,
        "exact_match": 2,
        "exact_match_percent": 50.0,
        "within_one": 3,
        "within_one_percent": 75.0,
        "mean_absolute_difference": 0.75,
        "mean_difference": 0.25,
        "max_absolute_difference": 2,
        "ours_higher": 1,
        "ours_lower": 1,
    }

    empty = summarize_pairs([])
    assert empty["count"] == 0
    assert empty["exact_match_percent"] is None


def test_functions_are_paired_by_line():
    ours = [
        {"qualified_name": "A.f", "start_line": 3, "cyclomatic_complexity": 2},
        {"qualified_name": "g", "start_line": 10, "cyclomatic_complexity": 1},
        {"qualified_name": "h", "start_line": 20, "cyclomatic_complexity": 4},
    ]
    theirs = [
        {"name": "f", "start_line": 3, "complexity": 2},
        {"name": "g", "start_line": 10, "complexity": 3},
        {"name": "extra", "start_line": 30, "complexity": 1},
    ]

    pairs, only_ours, only_radon = pair_functions(ours, theirs)

    assert pairs == [
        {"name": "A.f", "line": 3, "ours": 2, "radon": 2},
        {"name": "g", "line": 10, "ours": 1, "radon": 3},
    ]
    assert only_ours == ["h"]
    assert only_radon == ["extra"]


def test_missing_radon_is_reported(monkeypatch):
    monkeypatch.setattr(radon_comparison, "get_tool_version", lambda name: None)
    project = make_project({"a.py": "x = 1\n"})

    report = compare_project(project)

    assert report["status"] == "unavailable"
    assert "pip install radon" in report["note"]


@needs_radon
def test_real_radon_agrees_on_simple_functions():
    code = (
        "def f(a):\n"
        "    if a:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "\n"
        "def g(items):\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        if item:\n"
        "            total += 1\n"
        "    return total\n"
    )
    project = make_project({"a.py": code})

    report = compare_project(project)

    assert report["status"] == "ok"
    assert report["summary"]["count"] == 2
    assert report["summary"]["exact_match"] == 2
    assert report["summary"]["exact_match_percent"] == 100.0
    assert report["only_ours"] == []
    assert report["only_radon"] == []
    assert report["radon_errors"] == []