import json

import numpy as np
import pandas as pd

from data_science.recommendations import MIN_PROJECTS, build_recommendations

OK_TOOLS = json.dumps(
    {"ruff": {"status": "ok", "version": "1"}, "bandit": {"status": "ok", "version": "2"}},
    sort_keys=True,
)
RUFF_FAILED = json.dumps(
    {"ruff": {"status": "failed", "version": "1"}, "bandit": {"status": "ok", "version": "2"}},
    sort_keys=True,
)


def run(run_id, project, when, tools=OK_TOOLS):
    return {"run_id": run_id, "project_name": project, "analyzed_at": when, "tools_json": tools}


def stats(run_id, files, duplication, documentation):
    return {"run_id": run_id, "files_analyzed": files, "duplication_ratio": duplication,
            "documentation_coverage": documentation}


def found(run_id, source, rule, times=1, title=None):
    return [{"run_id": run_id, "source": source, "rule": rule, "title": title or f"{source} {rule}"}
            for _ in range(times)]


def tables():
    runs = pd.DataFrame([
        run("r0", "P1", "2026-10-01T10:00:00+00:00"),  # an old run: it must be ignored
        run("r1", "P1", "2026-11-01T10:00:00+00:00"),
        run("r2", "P2", "2026-11-01T10:00:00+00:00"),
        run("r3", "P3", "2026-11-01T10:00:00+00:00"),
        run("r4", "P4", "2026-11-01T10:00:00+00:00", tools=RUFF_FAILED),
    ])
    metrics = pd.DataFrame([
        stats("r0", 1, 0.0, 100.0),
        stats("r1", 3, 12.0, 20.0),
        stats("r2", 2, 3.0, 80.0),
        stats("r3", 1, np.nan, 25.0),
        stats("r4", 2, 0.0, 90.0),
    ])
    findings = pd.DataFrame(
        found("r0", "bandit", "B307")
        + found("r0", "validation", None, title="Syntax error")
        + found("r1", "static", "deep_nesting", 2)
        + found("r1", "static", "long_method")
        + found("r1", "ruff", "F401", 3)
        + found("r2", "static", "deep_nesting")
        + found("r2", "ruff", "F401")
        + found("r3", "static", "long_method")
    )
    return metrics, runs, findings


def test_recommendations_from_patterns():
    metrics, runs, findings = tables()

    result = build_recommendations(metrics, runs, findings)

    assert result["status"] == "ok"
    assert result["projects_total"] == 4
    assert result["basis"] == "the latest run of each project"

    assert [item["id"] for item in result["recommendations"]] == [
        "unused_imports", "deep_nesting", "long_method", "low_documentation",
    ]
    by_id = {item["id"]: item for item in result["recommendations"]}

    unused = by_id["unused_imports"]  # P4's Ruff failed, so only 3 projects could be measured
    assert (unused["projects_with"], unused["projects_total"], unused["share"]) == (2, 3, 0.667)
    assert unused["evidence"] == [{"project": "P1", "value": 3}, {"project": "P2", "value": 1}]
    assert unused["advice"]

    nesting = by_id["deep_nesting"]
    assert (nesting["projects_with"], nesting["projects_total"], nesting["share"]) == (2, 4, 0.5)
    assert nesting["evidence"] == [{"project": "P1", "value": 2}, {"project": "P2", "value": 1}]

    assert by_id["long_method"]["evidence"] == [
        {"project": "P1", "value": 1}, {"project": "P3", "value": 1}]
    assert by_id["low_documentation"]["evidence"] == [
        {"project": "P1", "value": 20.0}, {"project": "P3", "value": 25.0}]

    checked = {item["id"]: item for item in result["checked"]}
    assert len(checked) == 11
    assert (checked["duplication"]["projects_with"], checked["duplication"]["projects_total"]) == (1, 3)
    assert (checked["security"]["projects_with"], checked["security"]["projects_total"]) == (0, 4)
    assert checked["syntax_errors"]["projects_with"] == 0  # the old run is ignored
    assert "duplication" not in by_id  # in only 1 project


def test_not_enough_projects():
    metrics, runs, findings = tables()
    two = runs[runs["project_name"].isin(["P1", "P2"])]

    result = build_recommendations(metrics, two, findings)

    assert MIN_PROJECTS == 3
    assert result["status"] == "not_enough_data"
    assert result["projects_total"] == 2
    assert result["recommendations"] == []
    assert "At least 3" in result["note"]