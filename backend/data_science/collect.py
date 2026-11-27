"""Collect projects into the research database.

Usage:
  python -m data_science.collect <folder> [--each-subfolder] [--db data/research.db]
                                          [--ai] [--max-files 8] [--yes]
  python -m data_science.collect --repos <list.csv> [--db data/research.db]
                                          [--ai] [--max-files 8] [--yes]

<folder>: one project, or with --each-subfolder one project per subfolder.
--repos:  a CSV of PUBLIC GitHub repositories. Every row must record the licence you checked,
          who checked it and when. With --ai, only rows with ai_ok=yes are sent to the AI.
Only numbers, paths and titles are saved. The source code is not.
Every saved run is also written to collection_log.csv, next to the database.
"""
import argparse
import csv
import json
import os
from datetime import datetime, timezone

from ai_engine.config import ConfigError, create_provider, load_ai_config, load_env_file
from ai_engine.reviewer import DEFAULT_MAX_FILES
from data_science.dataset import build_analysis_table, dataset_summary
from data_science.store import ResearchStore, StoreError
from input_manager import from_local_folder
from input_manager.models import InputError
from input_manager.rules import IGNORED_FOLDERS
from repo_fetcher.github import FetchError, parse_github_url
from repo_fetcher.service import fetch_repository
from services.pipeline import run_pipeline

LOG_NAME = "collection_log.csv"
LOG_COLUMNS = [
    "collected_at", "run_id", "project_name", "source", "url", "archive_root",
    "licence", "checked_by", "checked_on", "ai_used", "files", "analysed", "issues", "note",
]
REQUIRED_COLUMNS = ("url", "licence", "checked_by", "checked_on")
NOT_A_LICENCE = ("", "unknown", "none", "n/a", "na", "?", "tbd")
YES_WORDS = ("yes", "y", "true", "1")


def find_targets(folder, each_subfolder) -> list:
    if not each_subfolder:
        return [folder]

    targets = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isdir(path) and not os.path.islink(path) and name.lower() not in IGNORED_FOLDERS:
            targets.append(path)
    return targets


def _ai_provider(args, project_count):
    """The AI provider if --ai was given and the user agrees. Otherwise None.
    Returns (provider, ok). ok is False when the run should stop."""
    if not args.ai:
        return None, True

    load_env_file()
    try:
        provider = create_provider(load_ai_config())
    except ConfigError as error:
        print(f"AI settings problem: {error}")
        return None, False
    if provider is None:
        print("AI review is off. Copy .env.example to .env and fill it in.")
        return None, False

    print(f"Provider: {provider.name}   Model: {provider.model}")
    print(f"Up to {args.max_files} files from each of {project_count} project(s) will be SENT.")
    if not args.yes and input("Send code to the AI service? [y/N] ").strip().lower() != "y":
        print("Cancelled. Nothing was sent.")
        return None, False
    return provider, True


# ---------- the list of repositories ----------

def read_repo_list(path):
    """Returns (rows, problems). A row without a recorded licence check is left out and explained."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            header = [(name or "").strip().lower() for name in (reader.fieldnames or [])]
            missing = [name for name in REQUIRED_COLUMNS if name not in header]
            if missing:
                return [], [f"The file has no column named: {', '.join(missing)}."]
            raw_rows = [
                {key.strip().lower(): (value or "").strip() for key, value in row.items() if key is not None}
                for row in reader
            ]
    except OSError:
        return [], ["The repository list could not be read."]

    rows, problems, seen = [], [], set()
    for number, row in enumerate(raw_rows, start=2):  # line 1 is the header
        label = f"row {number}"
        try:
            owner, repo = parse_github_url(row.get("url", ""))
        except FetchError as error:
            problems.append(f"{label}: {error}")
            continue

        key = (owner.lower(), repo.lower())
        if key in seen:
            problems.append(f"{label}: {owner}/{repo} is listed twice.")
            continue
        if row.get("licence", "").lower() in NOT_A_LICENCE:
            problems.append(f"{label}: no licence recorded for {owner}/{repo}. Look it up, then fill it in.")
            continue
        if not row.get("checked_by") or not row.get("checked_on"):
            problems.append(f"{label}: say who checked the licence and when.")
            continue

        seen.add(key)
        rows.append({
            "owner": owner,
            "repo": repo,
            "url": f"https://github.com/{owner}/{repo}",
            "licence": row["licence"],
            "checked_by": row["checked_by"],
            "checked_on": row["checked_on"],
            "ai_ok": row.get("ai_ok", "").lower() in YES_WORDS,
            "note": row.get("note", ""),
        })
    return rows, problems


# ---------- the collection log ----------

def append_log(db_path, entries) -> str:
    """Add rows to collection_log.csv next to the database. The header is written once."""
    path = os.path.join(os.path.dirname(os.path.abspath(db_path)), LOG_NAME)
    exists = os.path.exists(path) and os.path.getsize(path) > 0

    # utf-8-sig adds a mark so Excel reads the file right. Only at the start of a new file.
    with open(path, "a", encoding="utf-8" if exists else "utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=LOG_COLUMNS, restval="")
        if not exists:
            writer.writeheader()
        writer.writerows(entries)
    return path


def _log_entry(run_id, project_name, source, extra, result) -> dict:
    summary = result["extraction"]["summary"]
    ai_report = result["ai_report"]
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "project_name": project_name,
        "source": source,
        "ai_used": "yes" if ai_report and ai_report["status"] == "ok" else "no",
        "files": summary["files"],
        "analysed": summary["analyzed"],
        "issues": len(result["issues"]),
        **extra,
    }


# ---------- running ----------

def _save_project(store, project, provider, max_files, label):
    """Run the pipeline and save the result. Returns (result, run_id), or None if not saved."""
    result = run_pipeline(project, ai_provider=provider, ai_max_files=max_files)
    try:
        run_id = store.save_review(result["extraction"], result["issues"], result["ai_report"])
    except (StoreError, ValueError) as error:
        print(f"{label}: not saved ({error})")
        return None

    summary = result["extraction"]["summary"]
    print(
        f"{label}: {summary['files']} files, {summary['analyzed']} analysed, "
        f"{len(result['issues'])} issues, saved as run {run_id}"
    )
    return result, run_id


def _finish(store, args, total, log_entries) -> int:
    log_path = append_log(args.db, log_entries) if log_entries else None

    print(f"\nSaved {len(log_entries)} of {total} project(s) to {args.db}")
    if log_path:
        print(f"Log: {log_path}")
    print()
    print(json.dumps(dataset_summary(build_analysis_table(store)), indent=2))
    return 0 if log_entries else 1


def _collect_folder(args) -> int:
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

    try:
        store = ResearchStore(args.db)
    except StoreError as error:
        print(f"Database problem: {error}")
        return 1

    log_entries = []
    for target in targets:
        name = os.path.basename(os.path.normpath(target))
        try:
            project = from_local_folder(target)
        except InputError as error:
            print(f"{name}: skipped ({error})")
            continue

        outcome = _save_project(store, project, provider, args.max_files, name)
        if outcome is None:
            continue
        result, run_id = outcome
        extra = {"url": "", "archive_root": "", "licence": "", "checked_by": "", "checked_on": "", "note": ""}
        log_entries.append(_log_entry(run_id, project.project_name, "folder", extra, result))

    return _finish(store, args, len(targets), log_entries)


def _collect_repos(args, open_url) -> int:
    rows, problems = read_repo_list(args.repos)
    if problems:
        print("Rows left out:")
        for text in problems:
            print(f"  {text}")
    if not rows:
        print("No usable rows. Nothing was collected.")
        return 1

    provider = None
    if args.ai:
        allowed = [row for row in rows if row["ai_ok"]]
        if not allowed:
            print("No row has ai_ok=yes, so the AI review is not used.")
        else:
            provider, ok = _ai_provider(args, len(allowed))
            if not ok:
                return 1

    try:
        store = ResearchStore(args.db)
    except StoreError as error:
        print(f"Database problem: {error}")
        return 1

    log_entries = []
    for row in rows:
        label = f"{row['owner']}/{row['repo']}"
        try:
            project = fetch_repository(row["owner"], row["repo"], open_url)
        except FetchError as error:
            print(f"{label}: not fetched ({error})")
            continue

        project.project_name = label[:100]  # owner/repo, so equal repo names of two owners stay apart
        outcome = _save_project(store, project, provider if row["ai_ok"] else None, args.max_files, label)
        if outcome is None:
            continue
        result, run_id = outcome
        extra = {
            "url": row["url"],
            "archive_root": project.source_ref,
            "licence": row["licence"],
            "checked_by": row["checked_by"],
            "checked_on": row["checked_on"],
            "note": row["note"],
        }
        log_entries.append(_log_entry(run_id, project.project_name, "github", extra, result))

    return _finish(store, args, len(rows), log_entries)


def main(argv=None, open_url=None):
    """open_url: how to reach GitHub. None = the real network. Tests give a fake one."""
    parser = argparse.ArgumentParser(description="Collect projects into the research database.")
    parser.add_argument("folder", nargs="?")
    parser.add_argument("--repos", help="CSV list of public GitHub repositories with licence records")
    parser.add_argument("--db", default="data/research.db")
    parser.add_argument("--each-subfolder", action="store_true")
    parser.add_argument("--ai", action="store_true", help="also run the AI review")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--yes", action="store_true", help="do not ask before sending code")
    args = parser.parse_args(argv)

    if bool(args.folder) == bool(args.repos):
        print("Give either a folder or --repos <list.csv>, not both and not neither.")
        return 1
    if args.folder:
        return _collect_folder(args)
    return _collect_repos(args, open_url)


if __name__ == "__main__":
    raise SystemExit(main())