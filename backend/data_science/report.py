"""Write tables and figures about the research database.

Usage:  python -m data_science.report [--db data/research.db] [--out data/eda]
                                      [--boots 1000] [--seed 0]

The report holds numbers and warnings. It does not interpret anything.
Interpretation is for the researcher, after reading the code behind the numbers.
"""
import argparse
import os
import platform

import matplotlib
import numpy
import pandas
import scipy

from data_science import eda, plots
from data_science.dataset import build_analysis_table, dataset_summary
from data_science.store import ResearchStore, StoreError
from features.schema import FEATURE_NAMES

GROUP_FEATURES = ["max_cyclomatic_complexity", "code_smells_per_100_loc", "documentation_coverage"]

WARNINGS = [
    "Files from the same project are not independent. Intervals come from resampling whole "
    "projects. p-values from file-level tests are too optimistic.",
    "code_smells is built from our own rules, which read max function length, max complexity "
    "and max nesting depth. A link between those and code_smells is by design (by_design = True).",
    "Counts grow with file size. The _per_100_loc columns divide by code lines. "
    "loc is left out as a predictor for those columns.",
    "There are many pairs. Each interval is 95% on its own, with no correction. About 1 in 20 "
    "can exclude zero by chance. Treat results as leads, not as findings.",
    "A correlation does not show a cause.",
    "Each file content is counted once. Identical files in different projects count once.",
    "Only Python files are analysed, so nothing here says anything about other languages.",
    "Numbers depend on our own metric rules and thresholds, and on the tool versions saved "
    "in the runs table.",
]


def _block(frame) -> str:
    return "```\n" + frame.to_string(index=False) + "\n```"


def _group_row(result) -> dict:
    groups = "; ".join(
        f"{name}: n={info['n']}, median={info['median']}" for name, info in result["groups"].items()
    )
    small = "; ".join(f"{name}: n={count}" for name, count in result["small_groups"].items())
    return {
        "feature": result["feature"],
        "status": result["status"],
        "test": result["test"],
        "statistic": result["statistic"],
        "p_value": result["p_value"],
        "groups": groups,
        "left_out": small,
    }


def _write_markdown(path, parts):
    with open(path, "w", encoding="utf-8") as target:
        target.write("\n\n".join(parts) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the exploratory analysis report.")
    parser.add_argument("--db", default="data/research.db")
    parser.add_argument("--out", default="data/eda")
    parser.add_argument("--boots", type=int, default=eda.DEFAULT_BOOTSTRAPS)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    if args.boots < 20:
        print("--boots must be at least 20.")
        return 1
    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}. Run data_science.collect first.")
        return 1

    try:
        store = ResearchStore(args.db)
    except StoreError as error:
        print(f"Database problem: {error}")
        return 1

    table = build_analysis_table(store)
    if table.empty:
        print("The database has no files yet. Run data_science.collect first.")
        return 1

    summary = dataset_summary(table)
    analysed = eda.prepare_table(table)
    every_file = eda.prepare_table(table, analyzed_only=False)

    description = eda.describe_features(analysed)
    outliers = eda.find_outliers(analysed)
    rules = eda.rule_frequencies(store.read_table("findings"), every_file)
    top = eda.top_files(analysed, "max_cyclomatic_complexity", 5)

    enough = len(analysed) >= eda.MIN_FILES_FOR_STATS
    correlations = None
    groups = None
    if enough:
        correlations = eda.spearman_with_ci(
            analysed, eda.correlation_pairs(), n_boot=args.boots, seed=args.seed
        )
        groups = pandas.DataFrame(
            [_group_row(eda.compare_groups(analysed, name, "language")) for name in GROUP_FEATURES]
        )

    os.makedirs(args.out, exist_ok=True)

    def where(name):
        return os.path.join(args.out, name)

    description.to_csv(where("descriptive_stats.csv"), index=False)
    outliers.to_csv(where("outliers.csv"), index=False)
    rules.to_csv(where("rule_frequencies.csv"), index=False)
    if enough:
        correlations.to_csv(where("correlations.csv"), index=False)
        groups.to_csv(where("group_comparisons.csv"), index=False)

    plots.plot_histograms(analysed, FEATURE_NAMES, where("histograms.png"))
    plots.plot_correlation_heatmap(analysed, FEATURE_NAMES, where("correlations_heatmap.png"))
    plots.plot_top_rules(rules, where("top_rules.png"))

    parts = [
        "# Exploratory analysis report (numbers only, no interpretation)",
        "## Data\n```\n"
        + "\n".join(f"{key}: {value}" for key, value in summary.items() if key != "missing_percent")
        + f"\nfiles used for statistics (analysed, each content once): {len(analysed)}"
        + f"\nprojects among them: {analysed['project_name'].nunique()}\n```",
        "## Read this first\n" + "\n".join(f"- {text}" for text in WARNINGS),
        "## Descriptive statistics\n" + _block(description),
        "## Outliers (Tukey rule)\n" + _block(outliers),
        "## Most frequent findings\n" + _block(rules),
        "## Files with the highest max_cyclomatic_complexity\n" + _block(top),
    ]
    if enough:
        parts.append("## Correlations (Spearman, 95% interval from resampling projects)\n"
                     + _block(correlations))
        parts.append("## Group comparison by language\n" + _block(groups))
    else:
        parts.append(
            f"## Correlations and group tests\nToo little data for correlations and group tests: "
            f"{len(analysed)} files, at least {eda.MIN_FILES_FOR_STATS} needed."
        )
    parts.append(
        "## Settings\n```\n"
        f"resamples: {args.boots}\nseed: {args.seed}\n"
        f"minimum projects for intervals: {eda.MIN_PROJECTS_FOR_CI}\n"
        f"python: {platform.python_version()}\npandas: {pandas.__version__}\n"
        f"numpy: {numpy.__version__}\nscipy: {scipy.__version__}\n"
        f"matplotlib: {matplotlib.__version__}\n```"
    )
    parts.append(
        "## Figures\n- histograms.png\n- correlations_heatmap.png\n- top_rules.png"
    )

    _write_markdown(where("report.md"), parts)
    print(f"Report written to {where('report.md')}")
    if not enough:
        print(f"Only {len(analysed)} files. Correlations and group tests were skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())