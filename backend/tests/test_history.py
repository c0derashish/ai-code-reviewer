import json

import numpy as np
import pandas as pd
import pytest

from analyzer.static.integrations import tool_runner
from data_science.history import (
    METRICS,
    compare_runs,
    comparable_metrics,
    load_history,
    project_trends,
    run_metrics,
)
from data_science.store import ResearchStore
from input_manager import from_uploads
from services.pipeline import run_pipeline

FILE_COLUMNS = [
    "run_id", "file_id", "file_path", "content_sha256", "analysis_status", "loc",
    "comment_lines", "code_smells", "lint_violations", "security_findings",
    "duplication_ratio", "documentation_coverage", "max_cyclomatic_complexity",
    "max_nesting_depth",
]
FINDING_COLUMNS = ["run_id", "file_path", "source", "rule", "title"]

TOOLS = json.dumps(
    {"ruff": {"status": "ok", "version": "1"}, "bandit": {"status": "ok", "version": "2"}},
    sort_keys=True,
)
DUPLICATION = json.dumps(
    {"status": "ok", "version": "d1", "settings": {"min_tokens": 50, "min_lines": 5}}, sort_keys=True
)
THRESHOLDS = json.dumps({"max_parameters": 5}, sort_keys=True)

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
    "long_method_lines": 3, "max_parameters": 1, "max_nesting_depth": 1,
    "max_complexity": 3, "large_class_lines": 10, "large_class_methods": 1,
}


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def files_table(rows):
    full = []
    for row in rows:
        item = {name: np.nan for name in FILE_COLUMNS}
        item["file_id"] = f"{row['run_id']}/{row['file_path']}"
        item.update(row)
        full.append(item)
    return pd.DataFrame(full, columns=FILE_COLUMNS)


def findings_table(rows):
    return pd.DataFrame(
        [{"run_id": r, "file_path": p, "source": s, "rule": rule, "title": f"{s} {rule}"}
         for r, p, s, rule in rows],
        columns=FINDING_COLUMNS,
    )


def run_row(run_id, project="P", when="2026-11-01T10:00:00+00:00", **changes):
    row = {
        "run_id": run_id, "project_name": project, "analyzed_at": when,
        "metrics_version": "m1", "thresholds_json": THRESHOLDS,
        "tools_json": TOOLS, "duplication_json": DUPLICATION,
    }
    row.update(changes)
    return row


def analysed(run_id, path, sha, **values):
    return {"run_id": run_id, "file_path": path, "content_sha256": sha,
            "analysis_status": "analyzed", **values}


# ---------- numbers for one run ----------

def test_run_metrics_values():
    files = files_table([
        analysed("r1", "a.py", "h1", loc=10, comment_lines=2, code_smells=1, lint_violations=2,
                 security_findings=0, duplication_ratio=50.0, documentation_coverage=50.0,
                 max_cyclomatic_complexity=3, max_nesting_depth=1),
        analysed("r1", "b.py", "h2", loc=30, comment_lines=8, code_smells=3, lint_violations=1,
                 security_findings=1, duplication_ratio=0.0,
                 max_cyclomatic_complexity=8, max_nesting_depth=3),
        {"run_id": "r1", "file_path": "c.js", "content_sha256": "h3",
         "analysis_status": "not_analyzed"},
    ])

    result = run_metrics(pd.DataFrame([run_row("r1")]), files).iloc[0]

    assert result["files_analyzed"] == 2
    assert result["loc"] == 40
    assert result["smells"] == 4
    assert result["smells_per_100_loc"] == 10.0          # 4 / 40 * 100
    assert result["lint_per_100_loc"] == 7.5             # 3 / 40 * 100
    assert result["security_findings"] == 1
    assert result["duplication_ratio"] == 12.0           # (0.5 * 12 + 0 * 38) / 50 * 100
    assert result["documentation_coverage"] == 50.0      # b.py has none, so it is left out
    assert result["max_complexity"] == 8


def test_run_metrics_keep_missing_values_missing():
    files = files_table([
        analysed("r2", "a.py", "h1", loc=10, comment_lines=0, code_smells=1,
                 security_findings=0, duplication_ratio=0.0),  # lint was not measured
        {"run_id": "r3", "file_path": "x.js", "content_sha256": "h2",
         "analysis_status": "not_analyzed"},
    ])
    runs = pd.DataFrame([run_row("r2"), run_row("r3", when="2026-11-02T10:00:00+00:00")])

    result = run_metrics(runs, files)

    second = result[result["run_id"] == "r2"].iloc[0]
    assert pd.isna(second["lint_per_100_loc"])  # missing, not 0
    assert second["security_findings"] == 0
    assert second["smells_per_100_loc"] == 10.0

    third = result[result["run_id"] == "r3"].iloc[0]
    assert third["files_analyzed"] == 0
    assert all(pd.isna(third[name]) for name in METRICS)


# ---------- can two runs be compared? ----------

def test_comparable_metrics():
    base = pd.Series(run_row("a"))

    def other(**changes):
        return pd.Series(run_row("b", **changes))

    assert comparable_metrics(base, other()) == METRICS
    assert "smells_per_100_loc" not in comparable_metrics(
        base, other(thresholds_json=json.dumps({"max_parameters": 4})))

    new_ruff = json.dumps(
        {"ruff": {"status": "ok", "version": "9"}, "bandit": {"status": "ok", "version": "2"}},
        sort_keys=True)
    assert "lint_per_100_loc" not in comparable_metrics(base, other(tools_json=new_ruff))

    bandit_failed = json.dumps(
        {"ruff": {"status": "ok", "version": "1"}, "bandit": {"status": "failed", "version": "2"}},
        sort_keys=True)
    result = comparable_metrics(base, other(tools_json=bandit_failed))
    assert "security_findings" not in result
    assert "lint_per_100_loc" in result

    other_settings = json.dumps(
        {"status": "ok", "version": "d1", "settings": {"min_tokens": 80, "min_lines": 5}},
        sort_keys=True)
    assert "duplication_ratio" not in comparable_metrics(base, other(duplication_json=other_settings))

    assert comparable_metrics(base, other(metrics_version="m2")) == []

    broken = comparable_metrics(base, other(tools_json="not json"))
    assert "lint_per_100_loc" not in broken and "security_findings" not in broken
    assert "loc" in broken and "smells_per_100_loc" in broken


# ---------- change over time ----------

def metric_row(run_id, project, when, smells):
    row = {"run_id": run_id, "project_name": project, "analyzed_at": when,
           "files_analyzed": 2, "loc": 100, "smells": 0, "smells_per_100_loc": smells,
           "lint_per_100_loc": np.nan, "security_findings": np.nan,
           "duplication_ratio": 5.0, "documentation_coverage": 40.0, "max_complexity": 6}
    return row


def test_project_trends():
    metrics = pd.DataFrame([
        metric_row("r3", "P", "2026-11-03T10:00:00+00:00", 5.0),
        metric_row("r1", "P", "2026-11-01T10:00:00+00:00", 10.0),
        metric_row("r2", "P", "2026-11-02T10:00:00+00:00", 8.0),
        metric_row("x1", "R", "2026-11-01T10:00:00+00:00", 4.0),
        metric_row("x2", "R", "2026-11-02T10:00:00+00:00", 2.0),
        metric_row("q1", "Q", "2026-11-01T10:00:00+00:00", 1.0),
    ])
    runs = pd.DataFrame([
        run_row("r1", "P"), run_row("r2", "P"), run_row("r3", "P"),
        run_row("x1", "R"), run_row("x2", "R", thresholds_json=json.dumps({"max_parameters": 3})),
        run_row("q1", "Q"),
    ])

    trends = project_trends(metrics, runs)

    assert list(trends) == ["P", "Q", "R"]
    assert trends["Q"] == {"runs": 1, "status": "not_enough_runs"}

    p = trends["P"]
    assert (p["runs"], p["status"], p["first_run"], p["last_run"]) == (3, "ok", "r1", "r3")
    assert p["metrics"]["smells_per_100_loc"] == {
        "first": 10.0, "last": 5.0, "delta": -5.0, "comparable": True}
    assert p["metrics"]["loc"] == {"first": 100.0, "last": 100.0, "delta": 0.0, "comparable": True}
    lint = p["metrics"]["lint_per_100_loc"]
    assert (lint["first"], lint["last"], lint["delta"]) == (None, None, None)

    r = trends["R"]["metrics"]["smells_per_100_loc"]  # thresholds changed between the runs
    assert r == {"first": 4.0, "last": 2.0, "delta": None, "comparable": False}


# ---------- comparing two runs ----------

def two_run_tables():
    files = files_table([
        analysed("r1", "a.py", "h1", loc=10, code_smells=1, max_cyclomatic_complexity=2, max_nesting_depth=1),
        analysed("r1", "b.py", "h2", loc=30, code_smells=3, max_cyclomatic_complexity=8, max_nesting_depth=3),
        analysed("r1", "c.py", "h3", loc=5, code_smells=1, max_cyclomatic_complexity=2, max_nesting_depth=4),
        analysed("r2", "a.py", "h1", loc=10, code_smells=1, max_cyclomatic_complexity=2, max_nesting_depth=1),
        analysed("r2", "b.py", "h2b", loc=25, code_smells=1, max_cyclomatic_complexity=5, max_nesting_depth=2),
        analysed("r2", "d.py", "h4", loc=7, code_smells=1, max_cyclomatic_complexity=2, max_nesting_depth=1),
    ])
    findings = findings_table([
        ("r1", "a.py", "static", "long_method"),
        ("r1", "b.py", "static", "long_method"),
        ("r1", "b.py", "static", "long_method"),
        ("r1", "b.py", "ruff", "F401"),
        ("r1", "c.py", "static", "deep_nesting"),
        ("r1", "a.py", "ai", "ai_review"),
        ("r2", "a.py", "static", "long_method"),
        ("r2", "b.py", "static", "long_method"),
        ("r2", "b.py", "ruff", "F401"),
        ("r2", "b.py", "ruff", "F401"),
        ("r2", "d.py", "static", "long_method"),
        ("r2", "b.py", "ai", "ai_review"),
    ])
    return files, findings


def test_compare_runs():
    files, findings = two_run_tables()
    runs = pd.DataFrame([run_row("r1"), run_row("r2", when="2026-11-02T10:00:00+00:00")])

    result = compare_runs(files, findings, runs, "r1", "r2")

    assert result["comparable"] == METRICS
    assert result["files"] == {"unchanged": 1, "changed": 1, "added": 1, "removed": 1}
    assert result["changed_files"].to_dict("records") == [{
        "file_path": "b.py", "loc_before": 30, "loc_after": 25,
        "smells_before": 3, "smells_after": 1,
        "max_complexity_before": 8, "max_complexity_after": 5,
        "max_nesting_before": 3, "max_nesting_after": 2,
    }]
    assert result["smell_change"] == {"down": 1, "same": 0, "up": 0}
    assert result["findings"] == {
        "persistent": 3,        # a.py long_method 1, b.py long_method 1, b.py F401 1
        "resolved": 1,          # b.py had two long_method findings, now one
        "new": 1,               # b.py has one more F401
        "in_added_files": 1,    # d.py
        "in_removed_files": 1,  # c.py
        "sources_compared": ["bandit", "duplication", "ruff", "static", "validation"],
        "sources_skipped": [],
    }  # the AI findings are never counted


def test_compare_runs_skips_what_was_measured_differently():
    files, findings = two_run_tables()
    runs = pd.DataFrame([
        run_row("r1"),
        run_row("r2", when="2026-11-02T10:00:00+00:00", thresholds_json=json.dumps({"max_parameters": 3})),
    ])

    result = compare_runs(files, findings, runs, "r1", "r2")

    assert "smells_per_100_loc" not in result["comparable"]
    assert result["smell_change"] is None
    changed = result["changed_files"].iloc[0]
    assert pd.isna(changed["smells_before"]) and pd.isna(changed["smells_after"])
    assert changed["loc_before"] == 30

    assert result["findings"] == {
        "persistent": 1, "resolved": 0, "new": 1,
        "in_added_files": 0, "in_removed_files": 0,
        "sources_compared": ["bandit", "duplication", "ruff", "validation"],
        "sources_skipped": ["static"],
    }


# ---------- with a real database ----------

def pipeline(files, analyzed_at):
    project = from_uploads("demo", [(path, text.encode("utf-8")) for path, text in files.items()])
    result = run_pipeline(project, thresholds=LOW_LIMITS)
    result["extraction"]["run"]["analyzed_at"] = analyzed_at
    return result


def test_history_from_a_real_store(tmp_path):
    store = ResearchStore(tmp_path / "research.db")
    first = pipeline({"calc.py": CODE}, "2026-11-01T10:00:00+00:00")
    second = pipeline({"calc.py": "def f(x):\n    return x\n"}, "2026-11-02T10:00:00+00:00")
    for result in (second, first):  # saved in the wrong order on purpose
        store.save_review(result["extraction"], result["issues"], result["ai_report"])
    first_id = first["extraction"]["run"]["run_id"]
    second_id = second["extraction"]["run"]["run_id"]

    history = load_history(store)
    metrics = run_metrics(history["runs"], history["files"])

    assert list(metrics["run_id"]) == [first_id, second_id]
    one, two = metrics.iloc[0], metrics.iloc[1]
    assert (one["files_analyzed"], one["loc"], one["smells"]) == (1, 14, 7)
    assert one["smells_per_100_loc"] == 50.0
    assert pd.isna(one["lint_per_100_loc"]) and pd.isna(one["security_findings"])
    assert (one["duplication_ratio"], one["documentation_coverage"], one["max_complexity"]) == (0.0, 50.0, 4)
    assert (two["loc"], two["smells"], two["smells_per_100_loc"]) == (2, 0, 0.0)
    assert (two["documentation_coverage"], two["max_complexity"]) == (0.0, 1)

    trend = project_trends(metrics, history["runs"])["demo"]
    assert trend["runs"] == 2
    assert trend["metrics"]["smells_per_100_loc"] == {
        "first": 50.0, "last": 0.0, "delta": -50.0, "comparable": True}
    assert trend["metrics"]["lint_per_100_loc"]["comparable"] is False  # Ruff was not available

    change = compare_runs(history["files"], history["findings"], history["runs"], first_id, second_id)
    assert change["files"] == {"unchanged": 0, "changed": 1, "added": 0, "removed": 0}
    assert change["smell_change"] == {"down": 1, "same": 0, "up": 0}
    assert change["findings"]["resolved"] == 7
    assert change["findings"]["persistent"] == 0
    assert change["findings"]["sources_compared"] == ["duplication", "static", "validation"]
    assert change["findings"]["sources_skipped"] == ["bandit", "ruff"]