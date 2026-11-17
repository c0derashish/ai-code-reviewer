import numpy as np
import pandas as pd
from scipy import stats

from features.schema import FEATURE_NAMES

COUNT_OUTCOMES = ["code_smells", "lint_violations", "security_findings"]
DENSITY_OUTCOMES = [f"{name}_per_100_loc" for name in COUNT_OUTCOMES]

PREDICTORS = [
    "loc", "functions", "classes", "imports",
    "avg_function_length", "max_function_length",
    "avg_cyclomatic_complexity", "max_cyclomatic_complexity",
    "max_nesting_depth", "documentation_coverage", "duplication_ratio",
]

# Our smell rules read these three features directly. A link between them and
# code_smells exists by design, so it tells us nothing new.
SMELL_INPUTS = {"max_function_length", "max_cyclomatic_complexity", "max_nesting_depth"}
SMELL_OUTCOMES = {"code_smells", "code_smells_per_100_loc"}

MIN_FILES_FOR_STATS = 30
MIN_PROJECTS_FOR_CI = 10
MIN_PAIR_SIZE = 3
DEFAULT_BOOTSTRAPS = 1000

GROUP_WARNING = (
    "Files from the same project are not independent, so this p-value is too optimistic."
)

RESULT_COLUMNS = [
    "predictor", "outcome", "n", "rho", "ci_low", "ci_high",
    "ci_excludes_zero", "by_design", "ci_note",
]


def _number(value):
    """A rounded float, or None when the value is missing."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), 3)


def _numbers(table, name) -> pd.Series:
    return pd.to_numeric(table[name], errors="coerce")


# ---------- preparing the table ----------

def add_density_columns(table) -> pd.DataFrame:
    """Add "<count>_per_100_loc" columns. Missing when loc is 0 or missing."""
    result = table.copy()
    loc = _numbers(result, "loc")
    loc = loc.where(loc > 0)
    for name in COUNT_OUTCOMES:
        result[f"{name}_per_100_loc"] = _numbers(result, name) / loc * 100
    return result


def prepare_table(table, analyzed_only=True) -> pd.DataFrame:
    """Rows for statistics.

    Each file content (SHA-256) is kept once. If it appears in several runs, the row
    with the most measured features is kept. Identical files in different projects
    also count once. analyzed_only=False keeps files that could not be analysed.
    """
    rows = table.copy()
    if analyzed_only:
        rows = rows[rows["analysis_status"] == "analyzed"]

    rows = rows.assign(_filled=rows[FEATURE_NAMES].notna().sum(axis=1))
    rows = rows.sort_values(
        ["_filled", "run_id", "file_path"], ascending=[False, True, True]
    )
    rows = rows.drop_duplicates(subset="content_sha256", keep="first")
    rows = rows.drop(columns="_filled")
    rows = rows.sort_values(["project_name", "file_path"]).reset_index(drop=True)
    return add_density_columns(rows)


# ---------- describing the data ----------

def describe_features(table, features=FEATURE_NAMES) -> pd.DataFrame:
    rows = []
    for name in features:
        values = _numbers(table, name).dropna()
        missing = round(100 * (1 - len(values) / len(table)), 1) if len(table) > 0 else None

        row = {"feature": name, "n": len(values), "missing_percent": missing}
        if len(values) == 0:
            row.update(dict.fromkeys(["mean", "std", "min", "q1", "median", "q3", "max", "skew"]))
        else:
            row.update(
                {
                    "mean": _number(values.mean()),
                    "std": _number(values.std()),  # sample standard deviation
                    "min": _number(values.min()),
                    "q1": _number(values.quantile(0.25)),
                    "median": _number(values.median()),
                    "q3": _number(values.quantile(0.75)),
                    "max": _number(values.max()),
                    "skew": _number(values.skew()),
                }
            )
        rows.append(row)

    return pd.DataFrame(
        rows,
        columns=["feature", "n", "missing_percent", "mean", "std", "min",
                 "q1", "median", "q3", "max", "skew"],
    )


def find_outliers(table, features=FEATURE_NAMES) -> pd.DataFrame:
    """Tukey's rule: below Q1 - 1.5*IQR or above Q3 + 1.5*IQR.

    When most values are 0 the IQR is 0, and every non-zero value is flagged.
    iqr_is_zero marks those features. Read their counts with care.
    """
    rows = []
    for name in features:
        values = _numbers(table, name).dropna()
        row = {"feature": name, "n": len(values)}

        if len(values) < 4:
            row.update(dict.fromkeys(
                ["q1", "q3", "low_limit", "high_limit", "outliers", "outlier_percent", "iqr_is_zero"]
            ))
        else:
            q1, q3 = values.quantile(0.25), values.quantile(0.75)
            spread = q3 - q1
            low, high = q1 - 1.5 * spread, q3 + 1.5 * spread
            count = int(((values < low) | (values > high)).sum())
            row.update(
                {
                    "q1": _number(q1),
                    "q3": _number(q3),
                    "low_limit": _number(low),
                    "high_limit": _number(high),
                    "outliers": count,
                    "outlier_percent": round(100 * count / len(values), 1),
                    "iqr_is_zero": bool(spread == 0),
                }
            )
        rows.append(row)

    return pd.DataFrame(
        rows,
        columns=["feature", "n", "q1", "q3", "low_limit", "high_limit",
                 "outliers", "outlier_percent", "iqr_is_zero"],
    )


def top_files(table, feature, count=5) -> pd.DataFrame:
    """The files with the highest value. Ties are ordered by path."""
    data = table[["project_name", "file_path", feature]].copy()
    data[feature] = _numbers(data, feature)
    data = data.dropna(subset=[feature])
    data = data.sort_values([feature, "file_path"], ascending=[False, True]).head(count)
    return data.reset_index(drop=True)


def rule_frequencies(findings, table, top=15) -> pd.DataFrame:
    """Most frequent findings. Only files kept in `table` are counted.

    Findings of the validator and of the AI have no fixed rule, so they are
    named by their title (validator) or "category: <category>" (AI).
    """
    keys = table[["run_id", "file_id", "project_name"]]
    merged = findings.merge(keys, on=["run_id", "file_id"], how="inner")

    names = merged["rule"].fillna(merged["title"])
    is_ai = merged["source"] == "ai"
    merged["rule_name"] = names.where(~is_ai, "category: " + merged["category"].astype(str))

    counts = (
        merged.groupby(["source", "rule_name"])
        .agg(
            findings=("file_id", "size"),
            files_affected=("file_id", "nunique"),
            projects_affected=("project_name", "nunique"),
        )
        .reset_index()
    )
    counts = counts.sort_values(
        ["findings", "source", "rule_name"], ascending=[False, True, True]
    )
    return counts.head(top).reset_index(drop=True)


# ---------- correlations ----------

def correlation_pairs() -> list:
    """The pairs decided in advance (not picked after looking at the data)."""
    pairs = []
    for outcome in COUNT_OUTCOMES:
        for predictor in PREDICTORS:
            pairs.append((predictor, outcome))
    for outcome in DENSITY_OUTCOMES:
        for predictor in PREDICTORS:
            if predictor != "loc":  # loc is inside these columns, so the pair is skipped
                pairs.append((predictor, outcome))
    return pairs


def spearman_with_ci(
    table, pairs, n_boot=DEFAULT_BOOTSTRAPS, seed=0, min_projects=MIN_PROJECTS_FOR_CI
) -> pd.DataFrame:
    """Spearman correlation for each pair, with a 95% interval.

    Interval method: resample whole PROJECTS with replacement, n_boot times, compute
    the correlation each time, take the 2.5th and 97.5th percentiles. This respects
    that files from one project belong together. With fewer than min_projects
    projects no interval is given.
    The intervals are per pair and are not corrected for the number of pairs.
    """
    columns = sorted({name for pair in pairs for name in pair})
    data = table[columns].apply(pd.to_numeric, errors="coerce").reset_index(drop=True)
    projects = table["project_name"].reset_index(drop=True)

    point = data.corr(method="spearman", min_periods=MIN_PAIR_SIZE)
    present = data.notna().astype(int)
    pair_counts = present.T.dot(present)  # rows with both values, for every pair

    rows_of = projects.groupby(projects).indices  # project name -> row positions
    names = list(rows_of)

    note = None
    draws = None
    if len(names) < min_projects:
        note = f"fewer than {min_projects} projects ({len(names)}): no interval"
    else:
        rng = np.random.default_rng(seed)
        draws = np.full((n_boot, len(pairs)), np.nan)
        for b in range(n_boot):
            picked = rng.integers(0, len(names), size=len(names))
            positions = np.concatenate([rows_of[names[i]] for i in picked])
            matrix = data.iloc[positions].corr(method="spearman", min_periods=MIN_PAIR_SIZE)
            for k, (x, y) in enumerate(pairs):
                draws[b, k] = matrix.at[x, y]

    result = []
    for k, (x, y) in enumerate(pairs):
        row = {
            "predictor": x,
            "outcome": y,
            "n": int(pair_counts.at[x, y]),
            "rho": _number(point.at[x, y]),
            "ci_low": None,
            "ci_high": None,
            "ci_excludes_zero": None,
            "by_design": bool(x in SMELL_INPUTS and y in SMELL_OUTCOMES),
            "ci_note": note,
        }

        if note is None:
            usable = draws[~np.isnan(draws[:, k]), k]
            if len(usable) < 0.9 * n_boot:
                row["ci_note"] = "too many resamples had no correlation"
            else:
                low, high = np.percentile(usable, [2.5, 97.5])
                row["ci_low"] = _number(low)
                row["ci_high"] = _number(high)
                row["ci_excludes_zero"] = bool(low > 0 or high < 0)
        result.append(row)

    return pd.DataFrame(result, columns=RESULT_COLUMNS)


# ---------- comparing groups ----------

def compare_groups(table, feature, group_column="language", min_group_size=5) -> dict:
    """Compare a feature between groups (for example between languages).

    2 groups: Mann-Whitney U test. 3 or more: Kruskal-Wallis H test.
    Both compare ranks, so they do not need a normal distribution.
    Groups with fewer than min_group_size values are left out and listed.
    """
    data = table[[feature, group_column]].copy()
    data[feature] = _numbers(data, feature)
    data = data.dropna()

    groups = {}
    small = {}
    for name, values in data.groupby(group_column)[feature]:
        if len(values) >= min_group_size:
            groups[name] = values.to_numpy()
        else:
            small[name] = len(values)

    result = {
        "feature": feature,
        "group_column": group_column,
        "status": "ok",
        "test": None,
        "statistic": None,
        "p_value": None,
        "groups": {
            name: {"n": len(values), "median": float(np.median(values))}
            for name, values in groups.items()
        },
        "small_groups": small,
        "warning": GROUP_WARNING,
    }

    if len(groups) < 2:
        result["status"] = "not_enough_groups"
        return result
    # All values are the same, so there is nothing to compare.
    # New scipy versions return NaN here. Older ones raised an error.
    all_values = np.concatenate(list(groups.values()))
    if np.unique(all_values).size < 2:
        result["status"] = "no_variation"
        return result
    
    try:
        if len(groups) == 2:
            first, second = groups.values()
            result["test"] = "Mann-Whitney U"
            outcome = stats.mannwhitneyu(first, second, alternative="two-sided")
        else:
            result["test"] = "Kruskal-Wallis H"
            outcome = stats.kruskal(*groups.values())
    except ValueError:
        result["status"] = "no_variation"  # every value is the same
        return result

    result["statistic"] = round(float(outcome.statistic), 3)
    result["p_value"] = round(float(outcome.pvalue), 4)
    return result