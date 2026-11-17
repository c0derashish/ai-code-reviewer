import os

import pandas as pd
import pytest

from analyzer.static.integrations import tool_runner
from data_science.profile_report import main
from data_science.store import ResearchStore
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
    "long_method_lines": 3, "max_parameters": 1, "max_nesting_depth": 1,
    "max_complexity": 3, "large_class_lines": 10, "large_class_methods": 1,
}


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def save(store, name, code, when):
    project = from_uploads(name, [("calc.py", code.encode("utf-8"))])
    result = run_pipeline(project, thresholds=LOW_LIMITS)
    result["extraction"]["run"]["analyzed_at"] = when
    store.save_review(result["extraction"], result["issues"], result["ai_report"])


def test_report_on_a_small_database(tmp_path, capsys):
    db = str(tmp_path / "research.db")
    out = str(tmp_path / "profile")
    store = ResearchStore(db)
    save(store, "demo", CODE, "2026-11-01T10:00:00+00:00")
    save(store, "demo", "def f(x):\n    return x\n", "2026-11-02T10:00:00+00:00")
    save(store, "other", CODE, "2026-11-01T10:00:00+00:00")

    assert main(["--db", db, "--out", out]) == 0

    printed = capsys.readouterr().out
    assert "Report written to" in printed
    assert "Recommendations skipped" in printed
    assert {"report.md", "run_metrics.csv", "trends.csv", "recommendations.csv"} <= set(os.listdir(out))

    text = open(os.path.join(out, "report.md"), encoding="utf-8").read()
    assert "Read this first" in text
    assert "Not enough data" in text
    assert "demo: run" in text
    assert "smells_per_100_loc" in text
    assert "smell count in changed files: down 1, same 0, up 0" in text

    trends = pd.read_csv(os.path.join(out, "trends.csv"))
    assert set(trends["project"]) == {"demo"}  # "other" has only one run
    row = trends[(trends["project"] == "demo") & (trends["metric"] == "smells_per_100_loc")].iloc[0]
    assert (row["first"], row["last"], row["delta"], bool(row["comparable"])) == (50.0, 0.0, -50.0, True)

    assert len(pd.read_csv(os.path.join(out, "run_metrics.csv"))) == 3

    assert main(["--db", db, "--out", out, "--projects", "demo"]) == 0
    assert len(pd.read_csv(os.path.join(out, "run_metrics.csv"))) == 2


def test_report_needs_data(tmp_path, capsys):
    missing = tmp_path / "missing.db"
    assert main(["--db", str(missing), "--out", str(tmp_path / "x")]) == 1
    assert "Database not found" in capsys.readouterr().out
    assert not missing.exists()

    empty = str(tmp_path / "empty.db")
    ResearchStore(empty)
    assert main(["--db", empty, "--out", str(tmp_path / "y")]) == 1
    assert "no runs" in capsys.readouterr().out