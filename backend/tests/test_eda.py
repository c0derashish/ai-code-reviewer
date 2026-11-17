import numpy as np
import pandas as pd
import pytest

from data_science.eda import (
    add_density_columns,
    compare_groups,
    correlation_pairs,
    describe_features,
    find_outliers,
    prepare_table,
    rule_frequencies,
    spearman_with_ci,
    top_files,
)
from features.schema import FEATURE_NAMES


def make_table(rows):
    """A table like the real one: every feature column exists, missing unless given."""
    full = []
    for row in rows:
        item = {name: np.nan for name in FEATURE_NAMES}
        item["file_id"] = f"{row['run_id']}/{row['file_path']}"
        item["language"] = "python"
        item.update(row)
        full.append(item)
    return pd.DataFrame(full)


ROWS = [
    {"run_id": "r1", "project_name": "P", "file_path": "a.py", "content_sha256": "h1",
     "analysis_status": "analyzed", "loc": 10, "functions": 1},
    {"run_id": "r2", "project_name": "P", "file_path": "a.py", "content_sha256": "h1",
     "analysis_status": "analyzed", "loc": 10, "functions": 1, "lint_violations": 0},
    {"run_id": "r1", "project_name": "Q", "file_path": "c.py", "content_sha256": "h2",
     "analysis_status": "analyzed", "loc": 5},
    {"run_id": "r1", "project_name": "Q", "file_path": "bad.py", "content_sha256": "h3",
     "analysis_status": "not_analyzed"},
]


# ---------- preparing the table ----------

def test_prepare_table_keeps_each_content_once():
    result = prepare_table(make_table(ROWS))

    assert list(result["file_path"]) == ["a.py", "c.py"]
    assert list(result["run_id"]) == ["r2", "r1"]  # the more complete copy of a.py wins
    assert "code_smells_per_100_loc" in result.columns


def test_prepare_table_can_keep_not_analyzed_rows():
    result = prepare_table(make_table(ROWS), analyzed_only=False)

    assert list(result["file_path"]) == ["a.py", "bad.py", "c.py"]


def test_density_columns():
    table = pd.DataFrame({
        "loc": [50, 0, np.nan, 20],
        "code_smells": [2, 3, 1, 1],
        "lint_violations": [1, np.nan, np.nan, np.nan],
        "security_findings": [0, np.nan, np.nan, np.nan],
    })

    result = add_density_columns(table)

    smells = result["code_smells_per_100_loc"]
    assert smells.iloc[0] == 4.0
    assert pd.isna(smells.iloc[1])  # loc is 0
    assert pd.isna(smells.iloc[2])  # loc is missing
    assert smells.iloc[3] == 5.0
    assert result["lint_violations_per_100_loc"].iloc[0] == 2.0
    assert pd.isna(result["lint_violations_per_100_loc"].iloc[3])  # lint is missing
    assert result["security_findings_per_100_loc"].iloc[0] == 0.0
    assert "code_smells_per_100_loc" not in table.columns  # the input is not changed


# ---------- describing the data ----------

def test_describe_features():
    table = pd.DataFrame({
        "x": [1, 2, 3, 4, 10, np.nan, np.nan],
        "empty": [np.nan] * 7,
    })

    result = describe_features(table, ["x", "empty"]).set_index("feature")

    x = result.loc["x"]
    assert x["n"] == 5
    assert x["missing_percent"] == 28.6
    assert x["mean"] == 4.0
    assert x["std"] == 3.536
    assert (x["min"], x["q1"], x["median"], x["q3"], x["max"]) == (1.0, 2.0, 3.0, 4.0, 10.0)
    assert x["skew"] > 1  # one large value pulls the tail to the right

    empty = result.loc["empty"]
    assert empty["n"] == 0
    assert empty["missing_percent"] == 100.0
    assert pd.isna(empty["mean"])


def test_find_outliers():
    table = pd.DataFrame({
        "x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 100],
        "zeros": [0] * 9 + [5],
        "short": [1, 2, 3] + [np.nan] * 7,
    })

    result = find_outliers(table, ["x", "zeros", "short"]).set_index("feature")

    x = result.loc["x"]
    assert (x["q1"], x["q3"]) == (3.25, 7.75)
    assert (x["low_limit"], x["high_limit"]) == (-3.5, 14.5)
    assert x["outliers"] == 1
    assert x["outlier_percent"] == 10.0
    assert x["iqr_is_zero"] is False or x["iqr_is_zero"] == False  # noqa: E712

    zeros = result.loc["zeros"]
    assert zeros["outliers"] == 1
    assert bool(zeros["iqr_is_zero"]) is True

    assert result.loc["short"]["n"] == 3
    assert pd.isna(result.loc["short"]["outliers"])  # too few values


def test_top_files():
    table = pd.DataFrame({
        "project_name": ["P"] * 5,
        "file_path": ["a.py", "b.py", "c.py", "d.py", "e.py"],
        "x": [5, 9, 9, np.nan, 1],
    })

    result = top_files(table, "x", count=3)

    assert list(result["file_path"]) == ["b.py", "c.py", "a.py"]  # ties ordered by path
    assert list(result["x"]) == [9, 9, 5]


def test_rule_frequencies():
    findings = pd.DataFrame([
        {"run_id": "r1", "file_id": "f1", "source": "static", "rule": "long_method",
         "title": "Long method: a", "category": "code_smell"},
        {"run_id": "r1", "file_id": "f1", "source": "static", "rule": "long_method",
         "title": "Long method: b", "category": "code_smell"},
        {"run_id": "r1", "file_id": "f2", "source": "static", "rule": "long_method",
         "title": "Long method: c", "category": "code_smell"},
        {"run_id": "r1", "file_id": "f1", "source": "validation", "rule": None,
         "title": "Syntax error", "category": "bug"},
        {"run_id": "r1", "file_id": "f1", "source": "ai", "rule": "ai_review",
         "title": "free text", "category": "security"},
        {"run_id": "r2", "file_id": "f9", "source": "static", "rule": "long_method",
         "title": "not in the table", "category": "code_smell"},
    ])
    table = pd.DataFrame({
        "run_id": ["r1", "r1"], "file_id": ["f1", "f2"], "project_name": ["A", "B"],
    })

    result = rule_frequencies(findings, table)

    assert result.to_dict("records") == [
        {"source": "static", "rule_name": "long_method",
         "findings": 3, "files_affected": 2, "projects_affected": 2},
        {"source": "ai", "rule_name": "category: security",
         "findings": 1, "files_affected": 1, "projects_affected": 1},
        {"source": "validation", "rule_name": "Syntax error",
         "findings": 1, "files_affected": 1, "projects_affected": 1},
    ]


# ---------- correlations ----------

def test_correlation_pairs_list():
    pairs = correlation_pairs()

    assert len(pairs) == 63
    assert len(set(pairs)) == 63
    assert all(x != y for x, y in pairs)
    assert ("loc", "code_smells") in pairs
    assert ("loc", "code_smells_per_100_loc") not in pairs
    assert ("documentation_coverage", "lint_violations_per_100_loc") in pairs


def test_spearman_value_without_ci():
    table = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "y": [2, 1, 4, 3, 5],  # rank differences -1, 1, -1, 1, 0 give rho = 1 - 6*4/120 = 0.8
        "project_name": ["p"] * 5,
    })

    result = spearman_with_ci(table, [("x", "y")], n_boot=50)

    row = result.iloc[0]
    assert row["n"] == 5
    assert row["rho"] == pytest.approx(0.8)
    assert pd.isna(row["ci_low"]) and pd.isna(row["ci_high"])
    assert "projects" in row["ci_note"]


def test_spearman_ci_with_many_projects():
    projects = [f"p{number}" for number in range(12) for _ in range(3)]
    x = list(range(36))
    table = pd.DataFrame({
        "x": x,
        "up": [2 * value for value in x],
        "down": [-value for value in x],
        "project_name": projects,
    })

    result = spearman_with_ci(table, [("x", "up"), ("x", "down")], n_boot=100, seed=1)

    up, down = result.iloc[0], result.iloc[1]
    assert up["n"] == 36
    assert up["rho"] == pytest.approx(1.0)
    assert up["ci_low"] == pytest.approx(1.0, abs=1e-6)
    assert up["ci_high"] == pytest.approx(1.0, abs=1e-6)
    assert up["ci_excludes_zero"]
    assert down["rho"] == pytest.approx(-1.0)
    assert down["ci_excludes_zero"]
    assert pd.isna(up["ci_note"])


def test_by_design_flag():
    table = pd.DataFrame({
        "max_cyclomatic_complexity": [1, 2, 3, 4, 5, 6],
        "max_nesting_depth": [1, 1, 2, 3, 3, 4],
        "loc": [10, 20, 15, 40, 30, 50],
        "code_smells": [0, 1, 0, 2, 1, 3],
        "code_smells_per_100_loc": [0.0, 5.0, 0.0, 5.0, 3.3, 6.0],
        "lint_violations": [0, 0, 1, 0, 2, 1],
        "project_name": ["p"] * 6,
    })
    pairs = [
        ("max_cyclomatic_complexity", "code_smells"),
        ("loc", "code_smells"),
        ("max_nesting_depth", "lint_violations"),
        ("max_nesting_depth", "code_smells_per_100_loc"),
    ]

    result = spearman_with_ci(table, pairs, n_boot=20)

    assert list(result["by_design"]) == [True, False, False, True]


# ---------- comparing groups ----------

def test_compare_two_groups():
    table = pd.DataFrame({
        "x": [1, 2, 3, 4, 5, 6],
        "language": ["a"] * 3 + ["b"] * 3,
    })

    result = compare_groups(table, "x", "language", min_group_size=3)

    assert result["status"] == "ok"
    assert result["test"] == "Mann-Whitney U"
    assert result["p_value"] == pytest.approx(0.1)  # exact: 2 of the 20 ways to split 6 values
    assert result["groups"] == {"a": {"n": 3, "median": 2.0}, "b": {"n": 3, "median": 5.0}}
    assert "not independent" in result["warning"]


def test_compare_three_groups():
    table = pd.DataFrame({
        "x": list(range(1, 10)),
        "language": ["a"] * 3 + ["b"] * 3 + ["c"] * 3,
    })

    result = compare_groups(table, "x", "language", min_group_size=3)

    # rank sums 6, 15, 24: H = 12/(9*10) * (36 + 225 + 576)/3 - 3*10 = 7.2
    assert result["test"] == "Kruskal-Wallis H"
    assert result["statistic"] == pytest.approx(7.2)
    assert result["p_value"] == pytest.approx(0.0273, abs=1e-3)  # chi-square, 2 degrees of freedom


def test_compare_groups_edge_cases():
    one_group = pd.DataFrame({"x": [1, 2, 3], "language": ["a"] * 3})
    assert compare_groups(one_group, "x", "language", min_group_size=3)["status"] == "not_enough_groups"

    with_small_group = pd.DataFrame({
        "x": [1, 2, 3, 4, 5, 6, 7, 8],
        "language": ["a"] * 3 + ["b"] * 3 + ["c"] * 2,
    })
    result = compare_groups(with_small_group, "x", "language", min_group_size=3)
    assert result["status"] == "ok"
    assert result["small_groups"] == {"c": 2}
    assert set(result["groups"]) == {"a", "b"}

    no_variation = pd.DataFrame({"x": [1] * 9, "language": ["a"] * 3 + ["b"] * 3 + ["c"] * 3})
    result = compare_groups(no_variation, "x", "language", min_group_size=3)
    assert result["status"] == "no_variation"
    assert result["p_value"] is None