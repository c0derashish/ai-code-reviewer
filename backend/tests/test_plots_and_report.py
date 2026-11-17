import os

import numpy as np
import pandas as pd
import pytest

from analyzer.static.integrations import tool_runner
from data_science import plots
from data_science.report import main
from data_science.store import ResearchStore
from input_manager import from_uploads
from services.pipeline import run_pipeline

PNG_START = b"\x89PNG\r\n\x1a\n"

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
    "    def divide(self, a, b=1):",
    "        if b == 0:",
    "            return None",
    "        return a / b",
    "",
])


def is_png(path):
    with open(path, "rb") as source:
        return source.read(8) == PNG_START


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def test_plots_write_png_files(tmp_path):
    table = pd.DataFrame({
        "loc": [10, 20, 30, 40],
        "functions": [1, 2, 3, 5],
        "code_smells": [0, 1, 0, 2],
    })
    rules = pd.DataFrame({
        "source": ["static", "ruff"],
        "rule_name": ["long_method", "F401"],
        "findings": [5, 3],
    })

    features = ["loc", "functions", "code_smells"]
    paths = [
        plots.plot_histograms(table, features, str(tmp_path / "h.png")),
        plots.plot_correlation_heatmap(table, features, str(tmp_path / "c.png")),
        plots.plot_top_rules(rules, str(tmp_path / "r.png")),
    ]

    for path in paths:
        assert os.path.getsize(path) > 0
        assert is_png(path)


def test_plots_handle_empty_data(tmp_path):
    table = pd.DataFrame({"loc": [np.nan, np.nan], "functions": [np.nan, np.nan]})
    rules = pd.DataFrame({"source": [], "rule_name": [], "findings": []})

    features = ["loc", "functions"]
    paths = [
        plots.plot_histograms(table, features, str(tmp_path / "h.png")),
        plots.plot_correlation_heatmap(table, features, str(tmp_path / "c.png")),
        plots.plot_top_rules(rules, str(tmp_path / "r.png")),
    ]

    for path in paths:
        assert is_png(path)


def test_report_on_a_small_database(tmp_path, capsys):
    db = str(tmp_path / "research.db")
    out = str(tmp_path / "eda")
    store = ResearchStore(db)

    projects = {
        "alpha": {"calc.py": CODE, "bad.py": "def broken(:\n"},
        "beta": {"calc.py": CODE, "other.py": "x = 1\n"},
    }
    for name, files in projects.items():
        project = from_uploads(name, [(path, text.encode("utf-8")) for path, text in files.items()])
        result = run_pipeline(project)
        store.save_review(result["extraction"], result["issues"], result["ai_report"])

    code = main(["--db", db, "--out", out, "--boots", "20"])

    assert code == 0
    files = set(os.listdir(out))
    assert {
        "report.md", "descriptive_stats.csv", "outliers.csv", "rule_frequencies.csv",
        "histograms.png", "correlations_heatmap.png", "top_rules.png",
    } <= files
    assert "correlations.csv" not in files  # too few files for statistics

    text = open(os.path.join(out, "report.md"), encoding="utf-8").read()
    assert "Too little data for correlations and group tests" in text
    assert "Read this first" in text
    assert "by_design" in text
    assert "Only 2 files" in capsys.readouterr().out


def test_report_needs_an_existing_database(tmp_path, capsys):
    db = tmp_path / "missing.db"

    code = main(["--db", str(db), "--out", str(tmp_path / "eda")])

    assert code == 1
    assert "Database not found" in capsys.readouterr().out
    assert not db.exists()  # the report never creates a database