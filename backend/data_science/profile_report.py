"""Write the history and recommendation report.

Usage:  python -m data_science.profile_report [--db data/research.db] [--out data/profile]
                                              [--projects name1,name2]

It writes numbers and warnings. It gives no verdict on anyone's skill.
"""
import argparse
import os

import pandas as pd

from data_science.history import compare_runs, load_history, project_trends, run_metrics
from data_science.recommendations import MIN_PROJECTS, build_recommendations
from data_science.store import ResearchStore, StoreError

WARNINGS = [
    "A project is identified by its folder name. The same folder collected again is the same "
    "project. A renamed folder is a new project.",
    "Two runs are compared only for metrics that were measured the same way (same rules, thresholds, "
    "tool versions). Other metrics are marked not comparable and get no change value.",
    "A lower or higher number does not show better or worse skill. Code changes for many reasons.",
    "The AI review is not used here. Its findings differ from run to run.",
    "The data has no developer identity. This describes the projects in the database, or the "
    "ones chosen with --projects.",
    "The advice is rule-based. Nobody has tested whether it helps. The limits (3 projects, "
    "2 projects with the pattern, 40%) are our choices.",
]

TREND_COLUMNS = ["project", "metric", "runs", "first", "last", "delta", "comparable"]


def _block(frame) -> str:
    return "```\n" + frame.to_string(index=False) + "\n```"


def _trend_table(trends) -> pd.DataFrame:
    rows = []
    for project, trend in trends.items():
        if trend["status"] != "ok":
            continue
        for metric, values in trend["metrics"].items():
            rows.append({"project": project, "metric": metric, "runs": trend["runs"], **values})
    return pd.DataFrame(rows, columns=TREND_COLUMNS)


def _comparison_text(project, comparison) -> str:
    files = comparison["files"]
    findings = comparison["findings"]
    change = comparison["smell_change"]
    smells = (
        f"down {change['down']}, same {change['same']}, up {change['up']}"
        if change else "not comparable (different thresholds or rules)"
    )
    return "\n".join([
        f"{project}: run {comparison['older']} -> run {comparison['newer']}",
        f"  files: unchanged {files['unchanged']}, changed {files['changed']}, "
        f"added {files['added']}, removed {files['removed']}",
        f"  metrics measured the same way: {', '.join(comparison['comparable']) or 'none'}",
        f"  smell count in changed files: {smells}",
        f"  findings in files present in both runs: persistent {findings['persistent']}, "
        f"resolved {findings['resolved']}, new {findings['new']}",
        f"  findings in added files: {findings['in_added_files']}, "
        f"in removed files: {findings['in_removed_files']}",
        f"  sources compared: {', '.join(findings['sources_compared']) or 'none'}; "
        f"skipped: {', '.join(findings['sources_skipped']) or 'none'}",
    ])


def _recommendation_text(advice) -> str:
    if advice["status"] != "ok":
        return advice["note"]

    parts = [f"Basis: {advice['basis']}. Projects: {advice['projects_total']}."]
    if not advice["recommendations"]:
        parts.append("No pattern reached the limits, so there is no advice.")

    for item in advice["recommendations"]:
        evidence = ", ".join(f"{e['project']}: {e['value']}" for e in item["evidence"])
        parts.append(
            f"### {item['title']} ({item['id']})\n{item['advice']}\n"
            f"Seen in {item['projects_with']} of {item['projects_total']} projects "
            f"({item['share'] * 100:.0f}%). {evidence}"
        )

    checked = pd.DataFrame(advice["checked"])
    parts.append("All patterns that were checked:\n" + _block(checked))
    return "\n\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="History and recommendation report.")
    parser.add_argument("--db", default="data/research.db")
    parser.add_argument("--out", default="data/profile")
    parser.add_argument("--projects", default="", help="project names, separated by commas")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"Database not found: {args.db}. Run data_science.collect first.")
        return 1
    try:
        store = ResearchStore(args.db)
    except StoreError as error:
        print(f"Database problem: {error}")
        return 1

    history = load_history(store)
    runs, files, findings = history["runs"], history["files"], history["findings"]

    wanted = {name.strip() for name in args.projects.split(",") if name.strip()}
    if wanted:
        runs = runs[runs["project_name"].isin(wanted)]
        files = files[files["run_id"].isin(runs["run_id"])]
        findings = findings[findings["run_id"].isin(runs["run_id"])]

    if runs.empty:
        print("There are no runs for these projects yet. Run data_science.collect first.")
        return 1

    metrics = run_metrics(runs, files)
    trends = project_trends(metrics, runs)
    advice = build_recommendations(metrics, runs, findings)
    trend_table = _trend_table(trends)

    comparisons = []
    for project, group in runs.groupby("project_name"):
        if len(group) >= 2:
            older, newer = group.iloc[-2]["run_id"], group.iloc[-1]["run_id"]
            comparisons.append(_comparison_text(project, compare_runs(files, findings, runs, older, newer)))

    os.makedirs(args.out, exist_ok=True)
    metrics.to_csv(os.path.join(args.out, "run_metrics.csv"), index=False)
    trend_table.to_csv(os.path.join(args.out, "trends.csv"), index=False)
    pd.DataFrame(advice["recommendations"]).to_csv(
        os.path.join(args.out, "recommendations.csv"), index=False
    )

    with_history = sum(1 for trend in trends.values() if trend["status"] == "ok")
    parts = [
        "# Project history and recommendations (numbers only, no verdicts)",
        f"## Data\n```\nruns: {len(runs)}\nprojects: {runs['project_name'].nunique()}\n"
        f"projects with at least 2 runs: {with_history}\n```",
        "## Read this first\n" + "\n".join(f"- {text}" for text in WARNINGS),
        "## Runs\n" + _block(metrics),
        "## Change between the first and the last run of each project\n"
        + (_block(trend_table) if not trend_table.empty
           else "No project has 2 or more runs yet, so there is no history to compare."),
        "## The last two runs of each project\n"
        + ("\n\n".join(comparisons) if comparisons else "Nothing to compare yet."),
        "## Recommendations\n" + _recommendation_text(advice),
    ]
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as target:
        target.write("\n\n".join(parts) + "\n")

    print(f"Report written to {os.path.join(args.out, 'report.md')}")
    if with_history == 0:
        print("No project has 2 or more runs yet.")
    if advice["status"] != "ok":
        print(f"Recommendations skipped: fewer than {MIN_PROJECTS} projects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())