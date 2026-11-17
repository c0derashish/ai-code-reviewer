import json
import sqlite3

import pandas as pd
import pytest

from analyzer.static.integrations import tool_runner
from data_science.dataset import AI_COLUMNS, build_analysis_table, dataset_summary
from data_science.store import ResearchStore, StoreError
from features.schema import COLUMNS, FEATURE_NAMES
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
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def complete(self, system, user):
        if "File: calc.py" in user:
            issue = {
                "line": 11, "code_quote": "if b == 0:", "severity": "medium",
                "category": "bug", "title": "Division check is incomplete",
                "explanation": "Only zero is handled.", "confidence": "high",
            }
            return json.dumps({"issues": [issue]})
        return '{"issues": []}'


def pipeline(files, name="demo", ai=False):
    project = from_uploads(name, [(path, text.encode("utf-8")) for path, text in files.items()])
    provider = FakeProvider() if ai else None
    return run_pipeline(project, ai_provider=provider, thresholds=LOW_LIMITS)


def save(store, result):
    return store.save_review(result["extraction"], result["issues"], result["ai_report"])


def run_id_of(result):
    return result["extraction"]["run"]["run_id"]


@pytest.fixture
def two_runs(tmp_path):
    """Run A: calc.py + bad.py, with AI. Run B: calc.py + other.py, without AI."""
    store = ResearchStore(tmp_path / "research.db")
    run_a = pipeline({"calc.py": CODE, "bad.py": "def broken(:\n"}, name="demo", ai=True)
    run_b = pipeline({"calc.py": CODE, "other.py": "x = 1\n"}, name="second")
    save(store, run_a)
    save(store, run_b)
    return store, run_id_of(run_a), run_id_of(run_b)


# ---------- the database ----------

def test_new_store_has_empty_tables(tmp_path):
    store = ResearchStore(tmp_path / "data" / "research.db")  # the folder is created

    for name in ("runs", "file_features", "findings", "file_ai"):
        assert len(store.read_table(name)) == 0
    assert list(store.read_table("file_features").columns) == COLUMNS
    assert "run_id" in store.read_table("runs").columns

    with pytest.raises(ValueError):
        store.read_table("users; DROP TABLE runs")


def test_save_and_load_a_review(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    result = pipeline({"calc.py": CODE, "bad.py": "def broken(:\n"}, ai=True)

    run_id = save(store, result)
    assert run_id == run_id_of(result)

    runs = store.read_table("runs")
    assert len(runs) == 1
    run = runs.iloc[0]
    assert run["run_id"] == run_id
    assert run["project_name"] == "demo"
    assert (run["files"], run["analyzed"], run["not_analyzed"]) == (2, 1, 1)
    assert json.loads(run["thresholds_json"]) == LOW_LIMITS
    assert json.loads(run["tools_json"])["ruff"] == {"status": "unavailable", "version": None}
    ai = json.loads(run["ai_json"])
    assert (ai["status"], ai["provider"], ai["model"]) == ("ok", "fake", "fake-model")
    assert ai["files_reviewed"] == 2

    features = store.read_table("file_features")
    assert len(features) == 2
    calc = features[features["file_path"] == "calc.py"].iloc[0]
    assert (calc["functions"], calc["classes"], calc["code_smells"]) == (3, 1, 7)
    assert calc["duplication_ratio"] == 0.0
    assert pd.isna(calc["lint_violations"])  # Ruff was not available: missing, not 0
    assert len(calc["content_sha256"]) == 64
    bad = features[features["file_path"] == "bad.py"].iloc[0]
    assert bad["analysis_status"] == "not_analyzed"
    assert pd.isna(bad["loc"])

    findings = store.read_table("findings")
    assert len(findings) == 9
    assert findings["source"].value_counts().to_dict() == {"static": 7, "validation": 1, "ai": 1}
    ai_row = findings[findings["source"] == "ai"].iloc[0]
    assert (ai_row["file_path"], ai_row["line"]) == ("calc.py", 11)
    assert (ai_row["severity"], ai_row["category"], ai_row["confidence"]) == ("medium", "bug", "high")
    assert ai_row["line_moved"] == 0
    validation_row = findings[findings["source"] == "validation"].iloc[0]
    assert (validation_row["file_path"], validation_row["severity"]) == ("bad.py", "high")
    assert pd.isna(validation_row["rule"])

    file_ai = store.read_table("file_ai")
    assert len(file_ai) == 2
    assert set(file_ai["ai_reviewed"]) == {1}


def test_saving_the_same_run_twice_is_refused(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    result = pipeline({"calc.py": CODE})
    save(store, result)

    with pytest.raises(StoreError):
        save(store, result)

    assert len(store.read_table("runs")) == 1
    assert len(store.read_table("file_features")) == 1


def test_bad_input_is_refused_and_nothing_is_saved(tmp_path):
    store = ResearchStore(tmp_path / "research.db")

    result = pipeline({"calc.py": CODE})
    result["extraction"]["rows"][0]["loc"] = -1
    with pytest.raises(ValueError):
        save(store, result)

    result = pipeline({"calc.py": CODE})
    stray = dict(result["issues"][0])
    stray["file_path"] = "nope.py"
    result["issues"].append(stray)
    with pytest.raises(ValueError):
        save(store, result)

    assert len(store.read_table("runs")) == 0
    assert len(store.read_table("file_features")) == 0
    assert len(store.read_table("findings")) == 0


def test_a_changed_schema_is_detected(tmp_path):
    first = tmp_path / "a.db"
    ResearchStore(first)
    with sqlite3.connect(first) as connection:
        connection.execute("ALTER TABLE file_features ADD COLUMN extra INTEGER")
    connection.close()
    with pytest.raises(StoreError):
        ResearchStore(first)

    second = tmp_path / "b.db"
    ResearchStore(second)
    with sqlite3.connect(second) as connection:
        connection.execute("UPDATE meta SET value = 'old' WHERE key = 'schema_version'")
    connection.close()
    with pytest.raises(StoreError):
        ResearchStore(second)


def test_no_source_code_is_stored(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    code = CODE + "\nresult = eval(user_input)\n"
    save(store, pipeline({"calc.py": code}, ai=True))

    data = (tmp_path / "research.db").read_bytes()
    assert b"eval(user_input)" not in data
    assert b"def add(self" not in data


# ---------- the dataset ----------

def test_ai_columns_keep_zero_and_missing_apart(two_runs):
    store, run_a, run_b = two_runs
    table = build_analysis_table(store)

    assert len(table) == 4
    assert list(table.columns[: len(COLUMNS)]) == COLUMNS
    assert list(table.columns[-len(AI_COLUMNS):]) == AI_COLUMNS

    def row(run_id, path):
        return table[(table["run_id"] == run_id) & (table["file_path"] == path)].iloc[0]

    calc = row(run_a, "calc.py")  # reviewed, one finding
    assert calc["ai_reviewed"] == 1
    assert calc["ai_findings"] == 1
    assert calc["ai_cat_bug"] == 1
    assert calc["ai_cat_security"] == 0
    assert calc["ai_sev_medium"] == 1
    assert calc["ai_sev_high"] == 0

    bad = row(run_a, "bad.py")  # reviewed, nothing found: zero
    assert bad["ai_reviewed"] == 1
    assert bad["ai_findings"] == 0

    for path in ("calc.py", "other.py"):  # run B had no AI: missing
        unreviewed = row(run_b, path)
        assert unreviewed["ai_reviewed"] == 0
        assert all(pd.isna(unreviewed[column]) for column in AI_COLUMNS)


def test_dataset_summary(two_runs):
    store, _, _ = two_runs
    summary = dataset_summary(build_analysis_table(store))

    assert summary["runs"] == 2
    assert summary["projects"] == 2
    assert summary["files"] == 4
    assert summary["analyzed_files"] == 3
    assert summary["not_analyzed_files"] == 1
    assert summary["distinct_file_contents"] == 3  # calc.py is the same in both runs
    assert summary["repeated_contents"] == 1

    missing = summary["missing_percent"]
    assert set(missing) == set(FEATURE_NAMES)
    assert missing["loc"] == 0.0
    assert missing["duplication_ratio"] == 0.0
    assert missing["lint_violations"] == 100.0       # Ruff never ran
    assert missing["avg_function_length"] == 33.3    # other.py has no functions
    assert missing["documentation_coverage"] == 33.3  # other.py has nothing to document


def test_empty_store(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    table = build_analysis_table(store)

    assert len(table) == 0
    assert all(column in table.columns for column in AI_COLUMNS)
    assert dataset_summary(table) == {
        "runs": 0,
        "projects": 0,
        "files": 0,
        "analyzed_files": 0,
        "not_analyzed_files": 0,
        "distinct_file_contents": 0,
        "repeated_contents": 0,
        "missing_percent": {},
    }