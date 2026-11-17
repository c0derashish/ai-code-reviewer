import pandas as pd

from analyzer.findings import CATEGORIES, SEVERITIES
from features.schema import FEATURE_NAMES

# AI columns. They are kept apart from the static features and always start with "ai_".
AI_COLUMNS = (
    ["ai_findings"]
    + [f"ai_cat_{category}" for category in CATEGORIES]
    + [f"ai_sev_{severity}" for severity in SEVERITIES]
)


def _count_ai_findings(findings) -> dict:
    """{(run_id, file_id): {column: count}} for the AI findings."""
    counts = {}
    ai_rows = findings[findings["source"] == "ai"]

    for row in ai_rows.itertuples(index=False):
        entry = counts.setdefault((row.run_id, row.file_id), dict.fromkeys(AI_COLUMNS, 0))
        entry["ai_findings"] += 1
        if row.category in CATEGORIES:
            entry[f"ai_cat_{row.category}"] += 1
        if row.severity in SEVERITIES:
            entry[f"ai_sev_{row.severity}"] += 1
    return counts


def build_analysis_table(store) -> pd.DataFrame:
    """One row per file per run: the 17 features plus the AI columns.

    AI columns are 0 when the AI reviewed the file and found nothing,
    and missing (NaN) when the AI did not review the file.
    """
    table = store.read_table("file_features").merge(
        store.read_table("file_ai"), on=["run_id", "file_id"], how="left"
    )
    table["ai_reviewed"] = table["ai_reviewed"].fillna(0).astype(int)

    counts = _count_ai_findings(store.read_table("findings"))

    ai_rows = []
    for run_id, file_id, reviewed in zip(table["run_id"], table["file_id"], table["ai_reviewed"]):
        if reviewed == 1:
            ai_rows.append(counts.get((run_id, file_id), dict.fromkeys(AI_COLUMNS, 0)))
        else:
            ai_rows.append(dict.fromkeys(AI_COLUMNS, None))

    ai_frame = pd.DataFrame(ai_rows, columns=AI_COLUMNS, index=table.index)
    return pd.concat([table, ai_frame], axis=1)


def dataset_summary(table) -> dict:
    """Basic facts about the dataset. Missing percent is over analysed files only."""
    analyzed = table[table["analysis_status"] == "analyzed"]
    distinct = int(table["content_sha256"].nunique())

    missing = {}
    if len(analyzed) > 0:
        missing = {
            name: round(float(analyzed[name].isna().mean()) * 100, 1) for name in FEATURE_NAMES
        }

    return {
        "runs": int(table["run_id"].nunique()),
        "projects": int(table["project_name"].nunique()),  # by name. See the limits
        "files": len(table),
        "analyzed_files": len(analyzed),
        "not_analyzed_files": len(table) - len(analyzed),
        "distinct_file_contents": distinct,
        "repeated_contents": len(table) - distinct,
        "missing_percent": missing,
    }