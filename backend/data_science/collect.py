"""Collect real projects into the research database.

Usage:
  python -m data_science.collect <folder> [--each-subfolder] [--db data/research.db]
                                          [--ai] [--max-files 8] [--yes]

Without --each-subfolder the folder is one project. With it, every subfolder
is one project. Only numbers, paths and titles are saved. The source code is not.
"""
import argparse
import json
import os

from ai_engine.config import ConfigError, create_provider, load_ai_config, load_env_file
from ai_engine.reviewer import DEFAULT_MAX_FILES
from data_science.dataset import build_analysis_table, dataset_summary
from data_science.store import ResearchStore, StoreError
from input_manager import from_local_folder
from input_manager.models import InputError
from input_manager.rules import IGNORED_FOLDERS
from services.pipeline import run_pipeline


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect projects into the research database.")
    parser.add_argument("folder")
    parser.add_argument("--db", default="data/research.db")
    parser.add_argument("--each-subfolder", action="store_true")
    parser.add_argument("--ai", action="store_true", help="also run the AI review")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--yes", action="store_true", help="do not ask before sending code")
    args = parser.parse_args(argv)

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

    saved = 0
    for target in targets:
        name = os.path.basename(os.path.normpath(target))
        try:
            project = from_local_folder(target)
        except InputError as error:
            print(f"{name}: skipped ({error})")
            continue

        result = run_pipeline(project, ai_provider=provider, ai_max_files=args.max_files)
        try:
            run_id = store.save_review(result["extraction"], result["issues"], result["ai_report"])
        except (StoreError, ValueError) as error:
            print(f"{name}: not saved ({error})")
            continue

        summary = result["extraction"]["summary"]
        print(
            f"{name}: {summary['files']} files, {summary['analyzed']} analysed, "
            f"{len(result['issues'])} issues, saved as run {run_id}"
        )
        saved += 1

    print(f"\nSaved {saved} of {len(targets)} project(s) to {args.db}\n")
    print(json.dumps(dataset_summary(build_analysis_table(store)), indent=2))
    return 0 if saved > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())