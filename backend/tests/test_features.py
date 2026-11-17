import hashlib
import json
import platform
from datetime import datetime

from analyzer.languages import detect_project_languages
from analyzer.static.duplication import DUPLICATION_VERSION, find_duplicates
from analyzer.static.python.code_smells import DEFAULT_THRESHOLDS
from analyzer.static.runner import METRICS_VERSION, analyze_project
from analyzer.validation import validate_project
from features.extractor import extract_project_features
from features.schema import (
    COLUMNS,
    FEATURE_NAMES,
    FEATURES,
    SCHEMA_VERSION,
    SOURCES,
    validate_row,
)
from input_manager import from_uploads

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

A_CODE = "def add(a, b):\n    total = a + b\n    return total\n"
B_CODE = "# copy\ndef add(a,   b):\n\n    total = a + b   # sum\n    return total\n"


def make_project(files, thresholds=None):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    validate_project(project)
    analyze_project(project, thresholds)
    return project


def features_of(row):
    return {name: row[name] for name in FEATURE_NAMES}


# ---------- schema ----------

def test_schema_lists_the_17_features():
    assert FEATURE_NAMES == [
        "loc", "blank_lines", "comment_lines", "functions", "classes", "imports", "variables",
        "avg_function_length", "max_function_length",
        "avg_cyclomatic_complexity", "max_cyclomatic_complexity", "max_nesting_depth",
        "documentation_coverage", "duplication_ratio",
        "code_smells", "lint_violations", "security_findings",
    ]
    assert len(set(FEATURE_NAMES)) == 17
    for feature in FEATURES:
        assert feature["source"] in SOURCES
        assert feature["kind"] in ("int", "float")
        assert feature["description"]


# ---------- one file ----------

def test_features_of_an_analyzed_file():
    project = make_project({"calc.py": CODE})
    row = extract_project_features(project)["rows"][0]

    assert features_of(row) == {
        "loc": 14,
        "blank_lines": 5,
        "comment_lines": 0,
        "functions": 3,
        "classes": 1,
        "imports": 0,
        "variables": 1,
        "avg_function_length": 3.7,
        "max_function_length": 4,
        "avg_cyclomatic_complexity": 2.3,
        "max_cyclomatic_complexity": 4,
        "max_nesting_depth": 2,
        "documentation_coverage": 50.0,
        "duplication_ratio": None,   # the duplicate check was not run
        "code_smells": 0,
        "lint_violations": None,     # Ruff was not run
        "security_findings": None,   # Bandit was not run
    }


def test_metadata_columns():
    project = make_project({"calc.py": CODE})
    result = extract_project_features(
        project, run_id="run1", analyzed_at="2026-11-12T10:00:00+00:00"
    )
    row = result["rows"][0]

    assert row["run_id"] == "run1"
    assert row["project_id"] == project.project_id
    assert row["project_name"] == "demo"
    assert row["file_id"] == f"{project.project_id}/calc.py"
    assert row["file_path"] == "calc.py"
    assert row["language"] == "python"
    assert row["content_sha256"] == hashlib.sha256(CODE.encode("utf-8")).hexdigest()
    assert row["analysis_status"] == "analyzed"
    assert row["note"] is None


def test_smell_count_follows_the_thresholds():
    default = extract_project_features(make_project({"calc.py": CODE}))
    assert default["rows"][0]["code_smells"] == 0

    low = extract_project_features(make_project({"calc.py": CODE}, LOW_LIMITS))
    assert low["rows"][0]["code_smells"] == 7
    assert low["run"]["thresholds"] == LOW_LIMITS


def test_file_without_functions_has_missing_values():
    project = make_project({"a.py": "x = 1\n"})
    row = extract_project_features(project)["rows"][0]

    assert features_of(row) == {
        "loc": 1, "blank_lines": 0, "comment_lines": 0,
        "functions": 0, "classes": 0, "imports": 0, "variables": 1,
        "avg_function_length": None, "max_function_length": None,
        "avg_cyclomatic_complexity": None, "max_cyclomatic_complexity": None,
        "max_nesting_depth": 0,
        "documentation_coverage": None,
        "duplication_ratio": None,
        "code_smells": 0,
        "lint_violations": None,
        "security_findings": None,
    }


# ---------- files that cannot be analysed ----------

def test_files_that_are_not_analyzed_keep_a_row():
    project = make_project({
        "good.py": "x = 1\n",
        "bad.py": "def broken(:\n",
        "a.js": "var a = 1;\n",
    })
    result = extract_project_features(project)

    assert result["summary"] == {"files": 3, "analyzed": 1, "not_analyzed": 2}
    js, bad, good = result["rows"]

    assert js["file_path"] == "a.js"
    assert js["language"] == "javascript"
    assert js["analysis_status"] == "not_analyzed"
    assert js["note"] == "Static analysis is only available for Python files so far."
    assert all(js[name] is None for name in FEATURE_NAMES)

    assert bad["file_path"] == "bad.py"
    assert bad["analysis_status"] == "not_analyzed"
    assert "errors" in bad["note"]
    assert all(bad[name] is None for name in FEATURE_NAMES)

    assert good["analysis_status"] == "analyzed"
    assert good["note"] is None
    assert good["loc"] == 1


# ---------- tools and duplicates ----------

def make_findings(path):
    return [
        {"file_path": path, "source": "ruff", "rule": "F401", "line": 1, "column": 8,
         "message": "x"},
        {"file_path": path, "source": "ruff", "rule": "F841", "line": 2, "column": 1,
         "message": "y"},
        {"file_path": path, "source": "bandit", "rule": "B307", "line": 3, "column": 1,
         "message": "z"},
    ]


def tool_counts(project, reports):
    row = extract_project_features(project, tool_reports=reports)["rows"][0]
    return row["lint_violations"], row["security_findings"]


def test_tool_counts():
    project = make_project({"a.py": "x = 1\n"})
    result = project.get_file("a.py").analysis_result
    ok = {"status": "ok", "version": "1.0"}

    result["tool_findings"] = make_findings("a.py")
    assert tool_counts(project, {"ruff": ok, "bandit": ok}) == (2, 1)
    assert tool_counts(project, {"ruff": {"status": "failed", "version": "1.0"}, "bandit": ok}) == (None, 1)
    assert tool_counts(project, {"ruff": ok, "bandit": {"status": "unavailable", "version": None}}) == (2, None)
    assert tool_counts(project, None) == (None, None)

    result["tool_findings"] = []  # tools ran and found nothing
    assert tool_counts(project, {"ruff": ok, "bandit": ok}) == (0, 0)

    del result["tool_findings"]  # this file never went through the tools
    assert tool_counts(project, {"ruff": ok, "bandit": ok}) == (None, None)


def test_duplication_ratio_comes_from_the_report():
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project, min_tokens=10, min_lines=3)

    result = extract_project_features(project, duplication_report=report)
    ratios = {row["file_path"]: row["duplication_ratio"] for row in result["rows"]}
    assert ratios == {"a.py": 100.0, "b.py": 75.0}
    assert result["run"]["duplication"] == {
        "status": "ok",
        "version": DUPLICATION_VERSION,
        "settings": {"min_tokens": 10, "min_lines": 3},
    }

    skipped = {
        "status": "skipped",
        "version": DUPLICATION_VERSION,
        "settings": {"min_tokens": 10, "min_lines": 3},
        "files": {},
    }
    result = extract_project_features(project, duplication_report=skipped)
    assert all(row["duplication_ratio"] is None for row in result["rows"])


# ---------- the run record ----------

def test_run_information():
    project = make_project({"a.py": "x = 1\n"})
    result = extract_project_features(
        project, run_id="run1", analyzed_at="2026-11-12T10:00:00+00:00"
    )
    run = result["run"]

    assert result["schema_version"] == SCHEMA_VERSION
    assert run["run_id"] == "run1"
    assert run["analyzed_at"] == "2026-11-12T10:00:00+00:00"
    assert run["schema_version"] == SCHEMA_VERSION
    assert run["metrics_version"] == METRICS_VERSION
    assert run["python_version"] == platform.python_version()
    assert run["thresholds"] == DEFAULT_THRESHOLDS
    assert run["tools"] == {
        "ruff": {"status": "not_run", "version": None},
        "bandit": {"status": "not_run", "version": None},
    }
    assert run["duplication"] == {"status": "not_run", "version": None, "settings": None}

    reports = {"ruff": {"status": "ok", "version": "0.9.1", "note": None}}
    run = extract_project_features(project, tool_reports=reports)["run"]
    assert run["tools"]["ruff"] == {"status": "ok", "version": "0.9.1"}
    assert run["tools"]["bandit"] == {"status": "not_run", "version": None}


def test_default_run_id_and_time():
    project = make_project({"a.py": "x = 1\n"})
    result = extract_project_features(project)
    run = result["run"]

    assert len(run["run_id"]) == 12
    int(run["run_id"], 16)  # hex digits only. A wrong id raises an error here
    assert datetime.fromisoformat(run["analyzed_at"]).utcoffset().total_seconds() == 0
    assert result["rows"][0]["run_id"] == run["run_id"]


# ---------- rows follow the schema ----------

def test_rows_follow_the_schema():
    project = make_project({
        "calc.py": CODE,
        "a.js": "var a = 1;\n",
        "bad.py": "def broken(:\n",
    })
    for row in extract_project_features(project)["rows"]:
        assert list(row) == COLUMNS
        assert validate_row(row) == []


def test_validate_row_finds_problems():
    project = make_project({"calc.py": CODE})
    row = dict(extract_project_features(project)["rows"][0])
    assert validate_row(row) == []

    del row["loc"]
    row["extra"] = 1
    row["blank_lines"] = True
    row["functions"] = 2.5
    row["avg_function_length"] = float("nan")
    row["max_function_length"] = -1
    row["documentation_coverage"] = 101

    assert sorted(validate_row(row)) == sorted([
        "missing column: loc",
        "unknown column: extra",
        "blank_lines: must be a number",
        "functions: must be a whole number",
        "avg_function_length: must be a finite number",
        "max_function_length: must not be negative",
        "documentation_coverage: must be 0 to 100",
    ])


def test_result_is_json_safe_and_has_no_source_code():
    project = make_project({"calc.py": CODE})
    text = json.dumps(extract_project_features(project))

    assert "Module doc" not in text
    assert "class Calculator" not in text