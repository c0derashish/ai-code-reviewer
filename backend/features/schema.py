import math

# Changes whenever a column is added, removed or redefined.
SCHEMA_VERSION = "features-0.1"

# Columns that say WHICH file and WHICH run a row belongs to. They are not features.
METADATA_COLUMNS = [
    "run_id",
    "project_id",
    "project_name",
    "file_id",
    "file_path",
    "language",
    "content_sha256",
    "analysis_status",
    "note",
]

# Where a number comes from. Kept so numbers from different origins are never mixed up.
SOURCES = ["own_lines", "own_ast", "own_rules", "own_duplication", "ruff", "bandit"]


def _feature(name, kind, unit, source, description):
    return {
        "name": name,
        "kind": kind,  # "int" or "float"
        "unit": unit,
        "source": source,
        "description": description,
    }


FEATURES = [
    _feature("loc", "int", "lines", "own_lines",
             "Code lines: all lines minus blank lines and comment-only lines."),
    _feature("blank_lines", "int", "lines", "own_lines",
             "Lines with only spaces or tabs."),
    _feature("comment_lines", "int", "lines", "own_lines",
             "Lines whose first non-space character is #."),
    _feature("functions", "int", "count", "own_ast",
             "Functions and methods, async ones included."),
    _feature("classes", "int", "count", "own_ast",
             "Classes."),
    _feature("imports", "int", "count", "own_ast",
             "Names imported. 'import os, sys' counts as 2."),
    _feature("variables", "int", "count", "own_ast",
             "Different simple names that are assigned anywhere in the file."),
    _feature("avg_function_length", "float", "lines", "own_ast",
             "Mean length of the functions. Missing if the file has no functions."),
    _feature("max_function_length", "int", "lines", "own_ast",
             "Length of the longest function. Missing if the file has no functions."),
    _feature("avg_cyclomatic_complexity", "float", "points", "own_ast",
             "Mean cyclomatic complexity of the functions. Missing if there are none."),
    _feature("max_cyclomatic_complexity", "int", "points", "own_ast",
             "Highest cyclomatic complexity of one function. Missing if there are none."),
    _feature("max_nesting_depth", "int", "levels", "own_ast",
             "Deepest nesting of if, for, while, try, with in the whole file."),
    _feature("documentation_coverage", "float", "percent", "own_ast",
             "Percent of functions and classes that have a docstring. "
             "Missing if the file has none."),
    _feature("duplication_ratio", "float", "percent", "own_duplication",
             "Percent of non-blank lines inside a duplicated block (exact token match). "
             "Missing if the duplicate check did not run."),
    _feature("code_smells", "int", "count", "own_rules",
             "Findings from our five smell rules. Duplicates are not counted here."),
    _feature("lint_violations", "int", "count", "ruff",
             "Ruff F-rule findings. Missing if Ruff did not run."),
    _feature("security_findings", "int", "count", "bandit",
             "Bandit findings. Missing if Bandit did not run."),
]

FEATURE_NAMES = [feature["name"] for feature in FEATURES]
COLUMNS = METADATA_COLUMNS + FEATURE_NAMES


def _value_problem(feature, value):
    """Why a value is not allowed, or None if it is fine."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "must be a number"
    if not math.isfinite(value):
        return "must be a finite number"
    if feature["kind"] == "int" and not isinstance(value, int):
        return "must be a whole number"
    if value < 0:
        return "must not be negative"
    if feature["unit"] == "percent" and value > 100:
        return "must be 0 to 100"
    return None


def validate_row(row) -> list:
    """Check one row against the schema. Returns a list of problems. Empty = fine."""
    problems = []

    for name in COLUMNS:
        if name not in row:
            problems.append(f"missing column: {name}")
    for name in row:
        if name not in COLUMNS:
            problems.append(f"unknown column: {name}")

    for feature in FEATURES:
        name = feature["name"]
        if name not in row or row[name] is None:
            continue  # None means "not known". That is allowed
        problem = _value_problem(feature, row[name])
        if problem:
            problems.append(f"{name}: {problem}")

    return problems