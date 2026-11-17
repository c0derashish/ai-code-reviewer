"""Experiment B: human judging of review findings.

Usage:
  python -m data_science.judging export <folder> [--each-subfolder] [--per-source 30]
        [--seed 0] [--out data/judging] [--ai] [--max-files 8] [--yes] [--force]
  python -m data_science.judging score <sheet.csv> [<second_sheet.csv>]
        --key data/judging/judging_key.csv [--out data/judging/scores.csv]

The sheet for judges has NO source, rule or model column, so judges do not know who
made a finding. The key file maps item ids to sources. Keep it away from the judges.
"""
import argparse
import csv
import math
import os
import random
from collections import Counter

from ai_engine.reviewer import DEFAULT_MAX_FILES
from analyzer.static.python_analyzer import split_lines
from data_science.collect import _ai_provider, find_targets
from input_manager import from_local_folder
from input_manager.models import InputError
from services.pipeline import run_pipeline

SHEET_NAME = "judging_sheet.csv"
KEY_NAME = "judging_key.csv"

SHEET_COLUMNS = [
    "item_id", "project_name", "file_path", "line", "severity", "category",
    "title", "explanation", "suggestion", "code_context",
    "correct", "useful", "severity_fit", "judge", "notes",
]
KEY_COLUMNS = [
    "item_id", "source", "rule", "model", "prompt_version",
    "project_name", "file_path", "line", "severity", "category",
]
ANSWERS = {
    "correct": ("yes", "no", "unsure"),
    "useful": ("yes", "no"),
    "severity_fit": ("right", "too_high", "too_low"),
}

LINE_WIDTH = 200
Z = 1.96  # for a 95% interval


# ---------- building the items ----------

def code_context(source_code, line, radius=3) -> str:
    """The lines around a finding. The finding's own line starts with '>'."""
    lines = split_lines(source_code)
    if not lines:
        return ""

    line = min(max(line, 1), len(lines))
    start = max(1, line - radius)
    end = min(len(lines), line + radius)

    parts = []
    for number in range(start, end + 1):
        marker = ">" if number == line else " "
        parts.append(f"{marker} {number:>4} | {lines[number - 1][:LINE_WIDTH]}")
    return "\n".join(parts)


def source_of(issue) -> str:
    """Where an issue came from. Validation issues have no 'source', so we use the id."""
    return issue.get("source") or issue["id"].rsplit("-", 1)[0]


def build_items(project_name, project, result) -> list:
    """One item per issue of a pipeline run, with the code around it."""
    ai_report = result["ai_report"] or {}
    items = []

    for issue in result["issues"]:
        code_file = project.get_file(issue["file_path"])
        if code_file is None:
            continue

        source = source_of(issue)
        is_ai = source == "ai"
        items.append(
            {
                "project_name": project_name,
                "file_path": issue["file_path"],
                "line": int(issue["line"]),
                "severity": issue["severity"],
                "category": issue["category"],
                "title": str(issue["title"])[:200],
                "explanation": str(issue["explanation"])[:600],
                "suggestion": str(issue.get("suggestion") or "")[:300],
                "code_context": code_context(code_file.source_code, int(issue["line"])),
                "source": source,
                "rule": str(issue.get("rule") or ""),
                "model": (ai_report.get("model") or "") if is_ai else "",
                "prompt_version": (ai_report.get("prompt_version") or "") if is_ai else "",
            }
        )
    return items


def sample_items(items, per_source, seed) -> list:
    """Up to per_source items from every source, chosen with a fixed seed.

    Each group is sorted first, so the same seed always gives the same sample, whatever
    the input order. The result is shuffled, so the order does not show the source.
    The input items are not changed.
    """
    rng = random.Random(seed)

    by_source = {}
    for item in items:
        by_source.setdefault(item["source"], []).append(dict(item))

    chosen = []
    for source in sorted(by_source):
        group = sorted(
            by_source[source],
            key=lambda i: (i["project_name"], i["file_path"], i["line"], i["title"]),
        )
        chosen.extend(rng.sample(group, min(per_source, len(group))))

    rng.shuffle(chosen)
    for number, item in enumerate(chosen, start=1):
        item["item_id"] = f"J{number:04d}"
    return chosen


# ---------- files ----------

def write_csv(path, columns, rows):
    # utf-8-sig puts a mark at the start, so Excel reads accents and symbols correctly
    with open(path, "w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, extrasaction="ignore", restval="")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path) -> list:
    with open(path, encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write_files(items, folder, force):
    """Write the blind sheet and the key. Never replaces an existing file unless force."""
    os.makedirs(folder, exist_ok=True)
    sheet_path = os.path.join(folder, SHEET_NAME)
    key_path = os.path.join(folder, KEY_NAME)

    if not force:
        for path in (sheet_path, key_path):
            if os.path.exists(path):
                raise FileExistsError(
                    f"{path} already exists. Use --force to replace it. "
                    "A sheet that judges already filled would be lost."
                )

    write_csv(sheet_path, SHEET_COLUMNS, items)
    write_csv(key_path, KEY_COLUMNS, items)
    return sheet_path, key_path


# ---------- statistics ----------

def wilson_interval(successes, total):
    """95% Wilson interval for a share. None when there is nothing to count.

    It works well for small samples and for shares near 0 or 1.
    It treats items as independent. Findings in the same file or project are not.
    """
    if total == 0:
        return None

    p = successes / total
    z2 = Z * Z
    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    spread = Z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denominator
    return round(max(0.0, center - spread), 3), round(min(1.0, center + spread), 3)


def cohens_kappa(first, second):
    """Agreement of two judges beyond chance. 1 = perfect, 0 = chance, below 0 = worse.

    first, second: {item_id: label}. Only items that both judged are used.
    None when it is not defined (no common items, or both used one single label).
    """
    common = [item for item in first if first[item] and second.get(item)]
    if not common:
        return None

    n = len(common)
    agree = sum(1 for item in common if first[item] == second[item]) / n
    chance = sum(
        (sum(1 for i in common if first[i] == label) / n)
        * (sum(1 for i in common if second[i] == label) / n)
        for label in {first[i] for i in common} | {second[i] for i in common}
    )
    if chance == 1:
        return None
    return round((agree - chance) / (1 - chance), 3)


def _ratio(part, whole):
    return round(part / whole, 3) if whole else None


def clean_answer(column, value):
    """Returns (answer or None, was_invalid). Blank means not answered."""
    text = (value or "").strip().lower().replace(" ", "_")
    if text == "":
        return None, False
    if text in ANSWERS[column]:
        return text, False
    return None, True


def score_sheet(rows, key_rows) -> dict:
    """Join a filled sheet with the key. Returns the usable items and a count of problems."""
    key_by_id = {row["item_id"]: row for row in key_rows}
    problems = {"unknown_items": 0, "altered": 0, "duplicate_rows": 0, "invalid_answers": 0}
    seen = set()
    items = []

    for row in rows:
        item_id = (row.get("item_id") or "").strip()
        key = key_by_id.get(item_id)

        if key is None:
            problems["unknown_items"] += 1
            continue
        if item_id in seen:
            problems["duplicate_rows"] += 1
            continue
        seen.add(item_id)

        same_place = (
            (row.get("file_path") or "") == key["file_path"]
            and str(row.get("line") or "").strip() == str(key["line"])
        )
        if not same_place:
            problems["altered"] += 1
            continue

        item = {"item_id": item_id, "source": key["source"], "judge": (row.get("judge") or "").strip()}
        for column in ANSWERS:
            answer, invalid = clean_answer(column, row.get(column))
            item[column] = answer
            if invalid:
                problems["invalid_answers"] += 1
        items.append(item)

    return {"items": items, "problems": problems}


def _stats(group) -> dict:
    correct = [i["correct"] for i in group if i["correct"]]
    useful = [i["useful"] for i in group if i["useful"]]
    fit = [i["severity_fit"] for i in group if i["severity_fit"]]

    yes, no, unsure = correct.count("yes"), correct.count("no"), correct.count("unsure")
    useful_yes = useful.count("yes")
    correct_ci = wilson_interval(yes, len(correct))  # unsure counts as "not correct"
    useful_ci = wilson_interval(useful_yes, len(useful))

    return {
        "n_items": len(group),
        "n_judged": len(correct),
        "correct_yes": yes,
        "correct_no": no,
        "correct_unsure": unsure,
        "correct_rate": _ratio(yes, len(correct)),
        "correct_ci_low": correct_ci[0] if correct_ci else None,
        "correct_ci_high": correct_ci[1] if correct_ci else None,
        "precision_without_unsure": _ratio(yes, yes + no),
        "useful_n": len(useful),
        "useful_yes": useful_yes,
        "useful_rate": _ratio(useful_yes, len(useful)),
        "useful_ci_low": useful_ci[0] if useful_ci else None,
        "useful_ci_high": useful_ci[1] if useful_ci else None,
        "severity_n": len(fit),
        "severity_right": fit.count("right"),
        "severity_too_high": fit.count("too_high"),
        "severity_too_low": fit.count("too_low"),
    }


def summarize(items) -> dict:
    """Statistics for every source, in alphabetical order."""
    by_source = {}
    for item in items:
        by_source.setdefault(item["source"], []).append(item)
    return {source: _stats(group) for source, group in sorted(by_source.items())}


# ---------- the commands ----------

def _percent(value) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def _line_for(source, stats) -> str:
    interval = ""
    if stats["correct_ci_low"] is not None:
        interval = f" [{_percent(stats['correct_ci_low'])} to {_percent(stats['correct_ci_high'])}]"
    return (
        f"  {source:<12} items {stats['n_items']:>3}  judged {stats['n_judged']:>3}  "
        f"correct {_percent(stats['correct_rate'])}{interval}  "
        f"useful {_percent(stats['useful_rate'])}"
    )


def export_command(args) -> int:
    if args.per_source < 1:
        print("--per-source must be at least 1.")
        return 1
    if not os.path.isdir(args.folder):
        print("Folder not found.")
        return 1

    targets = find_targets(args.folder, args.each_subfolder)
    if not targets:
        print("No project folders found.")
        return 1

    provider, ok = _ai_provider(args, len(targets))
    if not ok:
        return 1

    items = []
    for target in targets:
        name = os.path.basename(os.path.normpath(target))
        try:
            project = from_local_folder(target)
        except InputError as error:
            print(f"{name}: skipped ({error})")
            continue

        result = run_pipeline(project, ai_provider=provider, ai_max_files=args.max_files)
        found = build_items(name, project, result)
        print(f"{name}: {len(found)} findings")
        items.extend(found)

    if not items:
        print("No findings to judge.")
        return 1

    chosen = sample_items(items, args.per_source, args.seed)
    try:
        sheet_path, key_path = write_files(chosen, args.out, args.force)
    except FileExistsError as error:
        print(error)
        return 1

    counts = Counter(item["source"] for item in chosen)
    summary = ", ".join(f"{source} {counts[source]}" for source in sorted(counts))
    print(f"\nSampled {len(chosen)} findings: {summary}")
    print(f"Sheet for judges: {sheet_path}")
    print(f"Key (keep it, judges must not see it): {key_path}")
    print("Both files contain code excerpts. Keep them private.")
    if not args.ai:
        print("Note: --ai was not given, so this sheet has no AI findings.")
    return 0


def score_command(args) -> int:
    try:
        key_rows = read_csv(args.key)
        sheets = [(path, read_csv(path)) for path in args.sheets]
    except OSError as error:
        print(f"Cannot read a file: {error}")
        return 1

    output_rows = []
    correct_by_sheet = []

    for path, rows in sheets:
        scored = score_sheet(rows, key_rows)
        stats = summarize(scored["items"])
        judges = sorted({item["judge"] for item in scored["items"] if item["judge"]})

        print(f"\nSheet: {os.path.basename(path)}   judge: {', '.join(judges) or '(not written)'}")
        print(f"  problems found while reading: {scored['problems']}")
        for source, values in stats.items():
            print(_line_for(source, values))
            output_rows.append({"sheet": os.path.basename(path), "source": source, **values})
        correct_by_sheet.append({i["item_id"]: i["correct"] for i in scored["items"]})

    if len(sheets) == 2:
        both = sum(1 for i, label in correct_by_sheet[0].items() if label and correct_by_sheet[1].get(i))
        kappa = cohens_kappa(correct_by_sheet[0], correct_by_sheet[1])
        shown = "not defined" if kappa is None else kappa
        print(f"\nAgreement on 'correct' (Cohen's kappa): {shown}  ({both} items judged by both)")

    if output_rows:
        columns = list(output_rows[0])
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        write_csv(args.out, columns, output_rows)
        print(f"\nWritten to {args.out}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Human judging of review findings (Experiment B).")
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="make a blind judging sheet")
    export.add_argument("folder")
    export.add_argument("--each-subfolder", action="store_true")
    export.add_argument("--per-source", type=int, default=30)
    export.add_argument("--seed", type=int, default=0)
    export.add_argument("--out", default="data/judging")
    export.add_argument("--ai", action="store_true", help="also run the AI review")
    export.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    export.add_argument("--yes", action="store_true", help="do not ask before sending code")
    export.add_argument("--force", action="store_true", help="replace an existing sheet")

    score = commands.add_parser("score", help="score one or two filled sheets")
    score.add_argument("sheets", nargs="+", help="one filled sheet, or two for agreement")
    score.add_argument("--key", required=True)
    score.add_argument("--out", default="data/judging/scores.csv")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "export":
        return export_command(args)
    if len(args.sheets) > 2:
        print("Give one or two sheets.")
        return 1
    return score_command(args)


if __name__ == "__main__":
    raise SystemExit(main())