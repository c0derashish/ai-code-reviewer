"""Experiment A: compare our function complexity with Radon's.

Run:  python -m analyzer.evaluation.radon_comparison <folder> [--top 10] [--json out.json]

It only measures AGREEMENT between two tools. Radon is not the truth.
"""
import argparse
import json

from analyzer.languages import detect_project_languages
from analyzer.static.integrations.tool_runner import get_tool_version
from analyzer.static.runner import METRICS_VERSION, analyze_project
from analyzer.validation import validate_project
from input_manager import from_local_folder
from input_manager.models import InputError


def _collect(block, found):
    """Radon gives classes and functions. We want every function."""
    if hasattr(block, "methods"):  # a class
        for method in block.methods:
            _collect(method, found)
        for inner_class in getattr(block, "inner_classes", []):
            _collect(inner_class, found)
    else:  # a function
        found.append(
            {"name": block.name, "start_line": block.lineno, "complexity": block.complexity}
        )
        for inner in getattr(block, "closures", []):
            _collect(inner, found)


def radon_functions(code):
    """Every function Radon sees in this code."""
    from radon.complexity import cc_visit  # imported here, so Radon stays optional

    found = []
    for block in cc_visit(code):
        _collect(block, found)
    return found


def pair_functions(our_functions, radon_list):
    """Match functions by the line of their "def". Returns (pairs, only_ours, only_radon)."""
    by_line = {item["start_line"]: item for item in radon_list}
    used = set()
    pairs = []
    only_ours = []

    for function in our_functions:
        match = by_line.get(function["start_line"])
        if match is None:
            only_ours.append(function["qualified_name"])
            continue
        used.add(function["start_line"])
        pairs.append(
            {
                "name": function["qualified_name"],
                "line": function["start_line"],
                "ours": function["cyclomatic_complexity"],
                "radon": match["complexity"],
            }
        )

    only_radon = [item["name"] for item in radon_list if item["start_line"] not in used]
    return pairs, only_ours, only_radon


def summarize_pairs(pairs):
    count = len(pairs)
    if count == 0:
        return {
            "count": 0, "exact_match": 0, "exact_match_percent": None,
            "within_one": 0, "within_one_percent": None,
            "mean_absolute_difference": None, "mean_difference": None,
            "max_absolute_difference": None, "ours_higher": 0, "ours_lower": 0,
        }

    differences = [pair["ours"] - pair["radon"] for pair in pairs]
    exact = sum(1 for d in differences if d == 0)
    within_one = sum(1 for d in differences if abs(d) <= 1)

    return {
        "count": count,
        "exact_match": exact,
        "exact_match_percent": round(exact / count * 100, 1),
        "within_one": within_one,
        "within_one_percent": round(within_one / count * 100, 1),
        "mean_absolute_difference": round(sum(abs(d) for d in differences) / count, 2),
        "mean_difference": round(sum(differences) / count, 2),  # ours minus Radon
        "max_absolute_difference": max(abs(d) for d in differences),
        "ours_higher": sum(1 for d in differences if d > 0),
        "ours_lower": sum(1 for d in differences if d < 0),
    }


def compare_project(project):
    """Run analyze_project(project) first."""
    version = get_tool_version("radon")
    if version is None:
        return {
            "status": "unavailable",
            "note": "radon is not installed. Install it with: pip install radon",
        }

    pairs, only_ours, only_radon, errors = [], [], [], []
    files_compared = 0

    for code_file in project.files:
        result = code_file.analysis_result
        if code_file.language != "python" or not result or result["status"] != "analyzed":
            continue

        try:
            theirs = radon_functions(code_file.source_code)
        except Exception:  # a third-party tool can fail in many ways. We record it and go on
            errors.append(code_file.file_path)
            continue

        files_compared += 1
        file_pairs, extra_ours, extra_radon = pair_functions(result["functions"], theirs)
        for pair in file_pairs:
            pair["file_path"] = code_file.file_path
        pairs.extend(file_pairs)
        only_ours.extend(f"{code_file.file_path}:{name}" for name in extra_ours)
        only_radon.extend(f"{code_file.file_path}:{name}" for name in extra_radon)

    return {
        "status": "ok",
        "radon_version": version,
        "metrics_version": METRICS_VERSION,
        "files_compared": files_compared,
        "pairs": pairs,
        "only_ours": only_ours,
        "only_radon": only_radon,
        "radon_errors": errors,
        "summary": summarize_pairs(pairs),
    }


def format_report(report, top=10):
    if report["status"] != "ok":
        return report["note"]

    summary = report["summary"]
    lines = [
        f"Radon version: {report['radon_version']}   Our metrics version: {report['metrics_version']}",
        f"Files compared: {report['files_compared']}   Functions matched: {summary['count']}",
        f"Only in our result: {len(report['only_ours'])}   "
        f"Only in Radon: {len(report['only_radon'])}   Radon errors: {len(report['radon_errors'])}",
    ]
    if summary["count"] == 0:
        lines.append("No functions to compare.")
        return "\n".join(lines)

    lines += [
        f"Exact match: {summary['exact_match']} ({summary['exact_match_percent']}%)",
        f"Within 1: {summary['within_one']} ({summary['within_one_percent']}%)",
        f"Mean absolute difference: {summary['mean_absolute_difference']}",
        f"Mean difference (ours - Radon): {summary['mean_difference']}",
        f"Ours higher: {summary['ours_higher']}   Ours lower: {summary['ours_lower']}",
        f"Largest difference: {summary['max_absolute_difference']}",
        "",
        f"Biggest differences (top {top}):",
    ]
    worst = sorted(report["pairs"], key=lambda pair: -abs(pair["ours"] - pair["radon"]))[:top]
    for pair in worst:
        lines.append(
            f"  {pair['file_path']}:{pair['line']} {pair['name']}  "
            f"ours={pair['ours']} radon={pair['radon']}"
        )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare our complexity numbers with Radon.")
    parser.add_argument("folder", help="a folder with Python code")
    parser.add_argument("--top", type=int, default=10, help="how many differences to list")
    parser.add_argument("--json", default=None, help="also save the full result to this file")
    args = parser.parse_args(argv)

    try:
        project = from_local_folder(args.folder)
    except InputError as error:
        print(f"Cannot read the folder: {error}")
        return 1

    detect_project_languages(project)
    validate_project(project)
    analyze_project(project)

    report = compare_project(project)
    print(format_report(report, args.top))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as target:
            json.dump(report, target, indent=2)
        print(f"\nSaved to {args.json}")

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())