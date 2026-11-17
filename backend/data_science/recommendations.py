import pandas as pd

from data_science.history import parse_json_dict

PROFILE_VERSION = "recommendations-0.1"

# Our starting values. They are choices, not standards.
MIN_PROJECTS = 3             # fewest projects needed to say anything
MIN_PROJECTS_WITH = 2        # a pattern must show up in at least this many projects
MIN_SHARE = 0.4              # ... and in at least this share of the projects it could be measured in
DUPLICATION_LIMIT = 10.0     # percent of lines. A project at or above it shows the pattern
DOCUMENTATION_LIMIT = 30.0   # percent. A project below it shows the pattern
MAX_EVIDENCE = 5

SYNTAX_TITLES = ("Syntax error", "Code cannot be compiled")
POSSIBLE_BUG_RULES = ("F821", "F811", "F632")

RULES = [
    {"id": "deep_nesting", "kind": "static", "title": "Deeply nested code",
     "advice": "Deeply nested code was found in several of your projects. Try returning early "
               "(guard clauses), or move the inner block into its own function. If the nesting "
               "is loops, also check how the running time grows with the input size."},
    {"id": "long_method", "kind": "static", "title": "Very long functions",
     "advice": "Very long functions appear in several projects. Split a long function into smaller "
               "ones that each do one job, and give them clear names."},
    {"id": "too_many_parameters", "kind": "static", "title": "Functions with many parameters",
     "advice": "Functions with many parameters appear in several projects. Group values that belong "
               "together into one object or dictionary, or split the function."},
    {"id": "high_complexity", "kind": "static", "title": "Functions with many decision paths",
     "advice": "Functions with many decision paths appear in several projects. Split them, simplify "
               "the conditions, and write one test for each path."},
    {"id": "large_class", "kind": "static", "title": "Very large classes",
     "advice": "Very large classes appear in several projects. Move related methods into smaller "
               "classes that each have one responsibility."},
    {"id": "duplication", "kind": "duplication", "title": "Copied code",
     "advice": "Copied code appears in several projects. Move the shared code into one function and "
               "call it from each place, so a fix is made only once."},
    {"id": "low_documentation", "kind": "documentation", "title": "Few docstrings",
     "advice": "Few functions and classes have docstrings in several projects. Add a short docstring "
               "that says what the function does, what it takes, and what it returns."},
    {"id": "unused_imports", "kind": "ruff", "rules": ("F401",), "title": "Unused imports",
     "advice": "Unused imports appear in several projects. Remove them, and turn on a linter in your "
               "editor so they are flagged while you type."},
    {"id": "possible_bugs_lint", "kind": "ruff", "rules": POSSIBLE_BUG_RULES,
     "title": "Likely mistakes found by a linter",
     "advice": "A linter found likely mistakes in several projects: names that are not defined, names "
               "defined twice, or 'is' used to compare values. Run a linter before you save or submit."},
    {"id": "security", "kind": "bandit", "title": "Risky calls flagged by a security checker",
     "advice": "A security checker flagged risky calls in several projects. Read each finding, check "
               "whether outside input can reach that line, and use the safer alternative it names."},
    {"id": "syntax_errors", "kind": "validation", "title": "Files Python cannot read",
     "advice": "Some files in several projects could not be read by Python. Run the code and a syntax "
               "check before you save or submit the project."},
]


def _latest_runs(runs) -> pd.DataFrame:
    ordered = runs.sort_values(["project_name", "analyzed_at", "run_id"])
    return ordered.groupby("project_name").tail(1)


def _count(findings, source, rules=None, titles=None) -> int:
    subset = findings[findings["source"] == source]
    if rules is not None:
        subset = subset[subset["rule"].isin(rules)]
    if titles is not None:
        subset = subset[subset["title"].isin(titles)]
    return len(subset)


def _check(rule, project) -> tuple:
    """(could it be measured, is the pattern present, the number shown as evidence)."""
    kind = rule["kind"]

    if kind == "static":
        count = _count(project["findings"], "static", rules=(rule["id"],))
        return project["files_analyzed"] >= 1, count >= 1, count
    if kind == "duplication":
        value = project["duplication_ratio"]
        if pd.isna(value):
            return False, False, None
        return True, value >= DUPLICATION_LIMIT, float(value)
    if kind == "documentation":
        value = project["documentation_coverage"]
        if pd.isna(value):
            return False, False, None
        return True, value < DOCUMENTATION_LIMIT, float(value)
    if kind == "ruff":
        count = _count(project["findings"], "ruff", rules=rule["rules"])
        return project["ruff_ok"], count >= 1, count
    if kind == "bandit":
        count = _count(project["findings"], "bandit")
        return project["bandit_ok"], count >= 1, count

    count = _count(project["findings"], "validation", titles=SYNTAX_TITLES)
    return True, count >= 1, count


def _project_data(metrics, runs, findings) -> dict:
    """What we need about the latest run of each project."""
    metrics_by_run = metrics.set_index("run_id")
    projects = {}

    for run in _latest_runs(runs).itertuples(index=False):
        tools = parse_json_dict(run.tools_json) or {}
        stats = metrics_by_run.loc[run.run_id]
        projects[run.project_name] = {
            "files_analyzed": int(stats["files_analyzed"]),
            "duplication_ratio": stats["duplication_ratio"],
            "documentation_coverage": stats["documentation_coverage"],
            "ruff_ok": (tools.get("ruff") or {}).get("status") == "ok",
            "bandit_ok": (tools.get("bandit") or {}).get("status") == "ok",
            "findings": findings[findings["run_id"] == run.run_id],
        }
    return projects


def build_recommendations(metrics, runs, findings) -> dict:
    """Advice based on the latest run of each project.

    A project counts for a pattern only if the pattern could be measured in it.
    Nothing here has been tested for whether the advice helps.
    """
    projects = _project_data(metrics, runs, findings)

    result = {
        "profile_version": PROFILE_VERSION,
        "basis": "the latest run of each project",
        "projects_total": len(projects),
        "status": "ok",
        "note": None,
        "recommendations": [],
        "checked": [],
    }

    if len(projects) < MIN_PROJECTS:
        result["status"] = "not_enough_data"
        result["note"] = (
            f"Not enough data: {len(projects)} project(s). At least {MIN_PROJECTS} are needed."
        )
        return result

    for rule in RULES:
        measured, shown = 0, []
        for name in sorted(projects):
            could, present, value = _check(rule, projects[name])
            if could:
                measured += 1
            if could and present:
                shown.append({"project": name, "value": value})

        share = round(len(shown) / measured, 3) if measured else None
        result["checked"].append(
            {"id": rule["id"], "projects_with": len(shown), "projects_total": measured, "share": share}
        )

        enough = len(shown) >= MIN_PROJECTS_WITH and share is not None and share >= MIN_SHARE
        if enough:
            result["recommendations"].append({
                "id": rule["id"],
                "title": rule["title"],
                "advice": rule["advice"],
                "projects_with": len(shown),
                "projects_total": measured,
                "share": share,
                "evidence": shown[:MAX_EVIDENCE],
            })

    result["recommendations"].sort(key=lambda item: (-item["share"], item["id"]))
    return result