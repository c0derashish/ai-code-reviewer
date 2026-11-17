import json
import os
import sqlite3
from contextlib import closing

import pandas as pd

from features.schema import COLUMNS, FEATURES, METADATA_COLUMNS, SCHEMA_VERSION, validate_row

# Each table is a list of (column name, SQL type). Names come from our own code only.
RUN_COLUMNS = [
    ("run_id", "TEXT PRIMARY KEY"),
    ("project_id", "TEXT"),
    ("project_name", "TEXT"),
    ("analyzed_at", "TEXT"),
    ("schema_version", "TEXT"),
    ("metrics_version", "TEXT"),
    ("python_version", "TEXT"),
    ("thresholds_json", "TEXT"),
    ("tools_json", "TEXT"),
    ("duplication_json", "TEXT"),
    ("ai_json", "TEXT"),
    ("files", "INTEGER"),
    ("analyzed", "INTEGER"),
    ("not_analyzed", "INTEGER"),
]

FILE_FEATURE_COLUMNS = [(name, "TEXT") for name in METADATA_COLUMNS] + [
    (feature["name"], "INTEGER" if feature["kind"] == "int" else "REAL")
    for feature in FEATURES
]

FINDING_COLUMNS = [
    ("run_id", "TEXT"),
    ("file_id", "TEXT"),
    ("file_path", "TEXT"),
    ("line", "INTEGER"),
    ("severity", "TEXT"),
    ("category", "TEXT"),
    ("source", "TEXT"),
    ("rule", "TEXT"),
    ("title", "TEXT"),
    ("confidence", "TEXT"),
    ("line_moved", "INTEGER"),
]

FILE_AI_COLUMNS = [("run_id", "TEXT"), ("file_id", "TEXT"), ("ai_reviewed", "INTEGER")]

# table name -> (columns, extra SQL)
TABLES = {
    "runs": (RUN_COLUMNS, ""),
    "file_features": (FILE_FEATURE_COLUMNS, "PRIMARY KEY (run_id, file_id)"),
    "findings": (FINDING_COLUMNS, ""),
    "file_ai": (FILE_AI_COLUMNS, "PRIMARY KEY (run_id, file_id)"),
}

MAX_TITLE_LENGTH = 200


class StoreError(Exception):
    """The database cannot be used, or the run cannot be saved."""


def _create_sql(table, columns, extra) -> str:
    body = ", ".join(f"{name} {kind}" for name, kind in columns)
    if extra:
        body += ", " + extra
    return f"CREATE TABLE IF NOT EXISTS {table} ({body})"


def _column_names(connection, table) -> list:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def _source_of(issue) -> str:
    """Where an issue came from. Older issue types have no "source" key,
    so we read it from the id: "validation-3" -> "validation"."""
    return issue.get("source") or issue["id"].rsplit("-", 1)[0]


def _lower_or_none(value):
    return str(value).lower() if value is not None else None


def _flag(value):
    return int(value) if value is not None else None


def _ai_info(ai_report) -> dict:
    if ai_report is None:
        return {"status": "not_run"}
    keys = (
        "status", "provider", "model", "prompt_version",
        "files_reviewed", "files_failed", "finding_count", "dropped",
    )
    return {key: ai_report[key] for key in keys}


def _ai_reviewed_paths(rows, ai_report) -> set:
    """Files the AI really looked at: every file that was neither skipped nor failed."""
    if ai_report is None or ai_report["status"] == "disabled":
        return set()
    left_out = {item["file_path"] for item in ai_report["files_skipped"]}
    left_out |= {item["file_path"] for item in ai_report["file_errors"]}
    return {row["file_path"] for row in rows} - left_out


def _insert(connection, table, values):
    names = list(values)
    marks = ", ".join("?" for _ in names)
    connection.execute(
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({marks})",
        [values[name] for name in names],
    )


class ResearchStore:
    """The research database. It holds numbers, paths and titles. No source code."""

    def __init__(self, path):
        self.path = str(path)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._prepare()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _prepare(self):
        """Create missing tables. Refuse a database made with another schema."""
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                for table, (columns, extra) in TABLES.items():
                    connection.execute(_create_sql(table, columns, extra))

                row = connection.execute(
                    "SELECT value FROM meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                        (SCHEMA_VERSION,),
                    )
                elif row[0] != SCHEMA_VERSION:
                    raise StoreError(
                        f"This database uses schema version {row[0]}. "
                        f"This code uses {SCHEMA_VERSION}."
                    )

                for table, (columns, _) in TABLES.items():
                    if _column_names(connection, table) != [name for name, _ in columns]:
                        raise StoreError(f"Table {table} does not match the current schema.")

    def read_table(self, name) -> pd.DataFrame:
        if name not in TABLES:
            raise ValueError(f"Unknown table: {name}")
        with closing(self._connect()) as connection:
            return pd.read_sql_query(f"SELECT * FROM {name}", connection)

    def save_review(self, extraction, issues, ai_report=None) -> str:
        """Save one review. Everything is saved or nothing is. Returns the run id.

        extraction: from features.extractor.extract_project_features
        issues:     all issues of the run (validation, static, tools, duplicates, AI)
        ai_report:  the report from ai_engine.reviewer, or None if the AI was not used
        """
        rows = extraction["rows"]
        run = extraction["run"]

        if not rows:
            raise ValueError("The extraction has no rows.")
        if extraction["schema_version"] != SCHEMA_VERSION:
            raise ValueError("The extraction uses another schema version.")
        for row in rows:
            problems = validate_row(row)
            if problems:
                raise ValueError(f"Row for {row.get('file_path')} breaks the schema: {problems[0]}")

        file_ids = {row["file_path"]: row["file_id"] for row in rows}
        for issue in issues:
            if issue["file_path"] not in file_ids:
                raise ValueError(f"An issue points to an unknown file: {issue['file_path']}")

        analyzed = sum(1 for row in rows if row["analysis_status"] == "analyzed")
        run_values = {
            "run_id": run["run_id"],
            "project_id": rows[0]["project_id"],
            "project_name": rows[0]["project_name"],
            "analyzed_at": run["analyzed_at"],
            "schema_version": run["schema_version"],
            "metrics_version": run["metrics_version"],
            "python_version": run["python_version"],
            "thresholds_json": json.dumps(run["thresholds"], sort_keys=True),
            "tools_json": json.dumps(run["tools"], sort_keys=True),
            "duplication_json": json.dumps(run["duplication"], sort_keys=True),
            "ai_json": json.dumps(_ai_info(ai_report), sort_keys=True),
            "files": len(rows),
            "analyzed": analyzed,
            "not_analyzed": len(rows) - analyzed,
        }
        reviewed = _ai_reviewed_paths(rows, ai_report)

        try:
            with closing(self._connect()) as connection:
                with connection:  # one transaction: all rows are saved, or none
                    _insert(connection, "runs", run_values)

                    for row in rows:
                        _insert(connection, "file_features", {name: row[name] for name in COLUMNS})
                        _insert(
                            connection,
                            "file_ai",
                            {
                                "run_id": run["run_id"],
                                "file_id": row["file_id"],
                                "ai_reviewed": int(row["file_path"] in reviewed),
                            },
                        )

                    for issue in issues:
                        _insert(
                            connection,
                            "findings",
                            {
                                "run_id": run["run_id"],
                                "file_id": file_ids[issue["file_path"]],
                                "file_path": issue["file_path"],
                                "line": int(issue["line"]),
                                "severity": issue["severity"],
                                "category": issue["category"],
                                "source": _source_of(issue),
                                "rule": issue.get("rule"),
                                "title": str(issue["title"])[:MAX_TITLE_LENGTH],
                                "confidence": _lower_or_none(issue.get("confidence")),
                                "line_moved": _flag(issue.get("line_moved")),
                            },
                        )
        except sqlite3.IntegrityError:
            raise StoreError("This run was already saved.") from None

        return run["run_id"]