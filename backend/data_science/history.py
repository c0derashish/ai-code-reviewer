import json

import pandas as pd

from data_science.dataset import build_analysis_table

# Project-level metrics, in the order they are shown.
METRICS = [
    "loc", "smells_per_100_loc", "lint_per_100_loc", "security_findings",
    "duplication_ratio", "documentation_coverage", "max_complexity",
]

# Which comparable metric each source of findings needs.
SOURCE_NEEDS = {
    "validation": "loc",  # "loc" is comparable only when the metric rules are the same
    "static": "smells_per_100_loc",
    "ruff": "lint_per_100_loc",
    "bandit": "security_findings",
    "duplication": "duplication_ratio",
}

RUN_COLUMNS = [
    "run_id", "project_name", "analyzed_at", "files_analyzed", "loc", "smells",
    "smells_per_100_loc", "lint_per_100_loc", "security_findings",
    "duplication_ratio", "documentation_coverage", "max_complexity",
]
CHANGED_COLUMNS = [
    "file_path", "loc_before", "loc_after", "smells_before", "smells_after",
    "max_complexity_before", "max_complexity_after", "max_nesting_before", "max_nesting_after",
]


def parse_json_dict(text):
    """A dictionary from JSON text, or None if the text is not a JSON object."""
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def load_history(store) -> dict:
    """The three tables the history analysis needs. Runs are sorted by project, then time."""
    runs = store.read_table("runs")
    runs = runs.sort_values(["project_name", "analyzed_at", "run_id"]).reset_index(drop=True)
    return {
        "runs": runs,
        "files": build_analysis_table(store),
        "findings": store.read_table("findings"),
    }


# ---------- numbers for one run ----------

def _numbers(group, name) -> pd.Series:
    return pd.to_numeric(group[name], errors="coerce")


def _total_or_none(values):
    """The sum, or None when there is nothing or any value is missing."""
    if len(values) == 0 or values.isna().any():
        return None
    return float(values.sum())


def _per_100(count, loc):
    if count is None or not loc:
        return None
    return round(count / loc * 100, 2)


def _whole(value):
    return int(round(value)) if value is not None else None


def _duplication(group):
    """Share of non-blank lines that are duplicated, weighted by file size.

    Weight = code lines + comment lines (that is all non-blank lines of the file).
    """
    ratio = _numbers(group, "duplication_ratio")
    weight = _numbers(group, "loc") + _numbers(group, "comment_lines")
    if ratio.isna().any() or weight.isna().any() or weight.sum() == 0:
        return None
    duplicated = (ratio / 100 * weight).sum()
    return round(float(duplicated / weight.sum() * 100), 1)


def _metrics_of(group) -> dict:
    loc = _total_or_none(_numbers(group, "loc"))
    smells = _total_or_none(_numbers(group, "code_smells"))
    lint = _total_or_none(_numbers(group, "lint_violations"))
    security = _total_or_none(_numbers(group, "security_findings"))

    coverage = _numbers(group, "documentation_coverage").dropna()
    complexity = _numbers(group, "max_cyclomatic_complexity").dropna()

    return {
        "files_analyzed": len(group),
        "loc": _whole(loc),
        "smells": _whole(smells),
        "smells_per_100_loc": _per_100(smells, loc),
        "lint_per_100_loc": _per_100(lint, loc),
        "security_findings": _whole(security),
        "duplication_ratio": _duplication(group),
        "documentation_coverage": round(float(coverage.mean()), 1) if len(coverage) else None,
        "max_complexity": int(complexity.max()) if len(complexity) else None,
    }


def run_metrics(runs, files) -> pd.DataFrame:
    """One row per run. Only analysed files count.

    A number is missing (not 0) when any analysed file of the run lacks it, for example
    when a tool did not run.
    """
    analysed = files[files["analysis_status"] == "analyzed"]
    groups = {run_id: group for run_id, group in analysed.groupby("run_id")}

    rows = []
    for run in runs.itertuples(index=False):
        group = groups.get(run.run_id)
        values = _metrics_of(group) if group is not None else {"files_analyzed": 0}
        rows.append(
            {"run_id": run.run_id, "project_name": run.project_name,
             "analyzed_at": run.analyzed_at, **values}
        )
    return pd.DataFrame(rows, columns=RUN_COLUMNS)


# ---------- can two runs be compared? ----------

def _tool_ok(tools, name):
    tool = (tools or {}).get(name)
    if isinstance(tool, dict) and tool.get("status") == "ok":
        return tool
    return None


def comparable_metrics(older, newer) -> list:
    """The metrics that two runs measured in the same way.

    A metric is comparable only if the rules and tools behind it were the same.
    older and newer are rows of the runs table.
    """
    if older["metrics_version"] != newer["metrics_version"]:
        return []

    names = ["loc", "documentation_coverage", "max_complexity"]

    if older["thresholds_json"] == newer["thresholds_json"]:
        names.append("smells_per_100_loc")

    tools_old = parse_json_dict(older["tools_json"])
    tools_new = parse_json_dict(newer["tools_json"])
    for tool, metric in (("ruff", "lint_per_100_loc"), ("bandit", "security_findings")):
        before, after = _tool_ok(tools_old, tool), _tool_ok(tools_new, tool)
        if before and after and before.get("version") == after.get("version"):
            names.append(metric)

    dup_old = parse_json_dict(older["duplication_json"])
    dup_new = parse_json_dict(newer["duplication_json"])
    if (
        dup_old and dup_new
        and dup_old.get("status") == "ok" and dup_new.get("status") == "ok"
        and dup_old.get("version") == dup_new.get("version")
        and dup_old.get("settings") == dup_new.get("settings")
    ):
        names.append("duplication_ratio")

    return [name for name in METRICS if name in names]


# ---------- change over time ----------

def _plain(value):
    return None if pd.isna(value) else float(value)


def project_trends(metrics, runs, min_runs=2) -> dict:
    """First run against last run of every project.

    A delta is given only when the metric is comparable between the two runs.
    A change says nothing about why it happened.
    """
    runs_by_id = runs.set_index("run_id")
    trends = {}

    for project, group in metrics.groupby("project_name"):
        group = group.sort_values(["analyzed_at", "run_id"])
        if len(group) < min_runs:
            trends[project] = {"runs": len(group), "status": "not_enough_runs"}
            continue

        first, last = group.iloc[0], group.iloc[-1]
        comparable = comparable_metrics(runs_by_id.loc[first["run_id"]], runs_by_id.loc[last["run_id"]])

        values = {}
        for name in METRICS:
            before, after = _plain(first[name]), _plain(last[name])
            can_compare = name in comparable
            delta = None
            if can_compare and before is not None and after is not None:
                delta = round(after - before, 2)
            values[name] = {"first": before, "last": after, "delta": delta, "comparable": can_compare}

        trends[project] = {
            "runs": len(group),
            "status": "ok",
            "first_run": first["run_id"],
            "last_run": last["run_id"],
            "first_time": first["analyzed_at"],
            "last_time": last["analyzed_at"],
            "metrics": values,
        }
    return trends


def _finding_counts(findings, run_id, sources) -> dict:
    """{(file_path, source, rule or title): how many}. AI findings are never included."""
    subset = findings[(findings["run_id"] == run_id) & findings["source"].isin(sources)]
    has_rule = subset["rule"].notna() & (subset["rule"] != "")
    names = subset["rule"].where(has_rule, subset["title"])

    counts = {}
    for key in zip(subset["file_path"], subset["source"], names):
        counts[key] = counts.get(key, 0) + 1
    return counts


def compare_runs(files, findings, runs, older_id, newer_id) -> dict:
    """What changed between two runs of the same project."""
    run_rows = runs.set_index("run_id")
    comparable = comparable_metrics(run_rows.loc[older_id], run_rows.loc[newer_id])

    old = files[files["run_id"] == older_id].set_index("file_path")
    new = files[files["run_id"] == newer_id].set_index("file_path")
    in_both = sorted(set(old.index) & set(new.index))
    added = sorted(set(new.index) - set(old.index))
    removed = sorted(set(old.index) - set(new.index))
    changed = [p for p in in_both if old.at[p, "content_sha256"] != new.at[p, "content_sha256"]]

    # before and after, for changed files that were analysed in both runs
    smells_ok = "smells_per_100_loc" in comparable
    rows = []
    for path in changed:
        if old.at[path, "analysis_status"] != "analyzed" or new.at[path, "analysis_status"] != "analyzed":
            continue
        rows.append({
            "file_path": path,
            "loc_before": old.at[path, "loc"], "loc_after": new.at[path, "loc"],
            "smells_before": old.at[path, "code_smells"] if smells_ok else None,
            "smells_after": new.at[path, "code_smells"] if smells_ok else None,
            "max_complexity_before": old.at[path, "max_cyclomatic_complexity"],
            "max_complexity_after": new.at[path, "max_cyclomatic_complexity"],
            "max_nesting_before": old.at[path, "max_nesting_depth"],
            "max_nesting_after": new.at[path, "max_nesting_depth"],
        })
    changed_frame = pd.DataFrame(rows, columns=CHANGED_COLUMNS)

    smell_change = None
    if smells_ok:
        before, after = changed_frame["smells_before"], changed_frame["smells_after"]
        smell_change = {
            "down": int((after < before).sum()),
            "same": int((after == before).sum()),
            "up": int((after > before).sum()),
        }

    # findings: only from sources that were measured in the same way in both runs
    included = [source for source, needed in SOURCE_NEEDS.items() if needed in comparable]
    old_counts = _finding_counts(findings, older_id, included)
    new_counts = _finding_counts(findings, newer_id, included)

    present_in_both, in_added, in_removed = set(in_both), set(added), set(removed)
    totals = {"persistent": 0, "resolved": 0, "new": 0, "in_added_files": 0, "in_removed_files": 0}
    for key in set(old_counts) | set(new_counts):
        path = key[0]
        before, after = old_counts.get(key, 0), new_counts.get(key, 0)
        if path in present_in_both:
            totals["persistent"] += min(before, after)
            totals["resolved"] += max(0, before - after)
            totals["new"] += max(0, after - before)
        elif path in in_added:
            totals["in_added_files"] += after
        elif path in in_removed:
            totals["in_removed_files"] += before

    return {
        "older": older_id,
        "newer": newer_id,
        "comparable": comparable,
        "files": {
            "unchanged": len(in_both) - len(changed),
            "changed": len(changed),
            "added": len(added),
            "removed": len(removed),
        },
        "changed_files": changed_frame,
        "smell_change": smell_change,
        "findings": {
            **totals,
            "sources_compared": sorted(included),
            "sources_skipped": sorted(set(SOURCE_NEEDS) - set(included)),
        },
    }