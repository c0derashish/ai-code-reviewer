"""Run the AI review on a local folder.

Usage:  python -m ai_engine.cli <folder> [--max-files 2] [--yes]
"""
import argparse

from ai_engine.config import ConfigError, create_provider, load_ai_config, load_env_file
from ai_engine.reviewer import DEFAULT_MAX_FILES, review_project
from analyzer.findings import ai_to_issues, static_to_issues, validation_to_issues
from analyzer.languages import detect_project_languages
from analyzer.static.runner import analyze_project
from analyzer.validation import validate_project
from input_manager import from_local_folder
from input_manager.models import InputError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the AI review on a local folder.")
    parser.add_argument("folder", help="a folder with source code")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--yes", action="store_true", help="do not ask before sending code")
    args = parser.parse_args(argv)

    load_env_file()  # reads .env in the current folder
    try:
        config = load_ai_config()
    except ConfigError as error:
        print(f"AI settings problem: {error}")
        return 1

    provider = create_provider(config)
    if provider is None:
        print("AI review is off. Copy .env.example to .env and fill it in.")
        return 1

    try:
        project = from_local_folder(args.folder)
    except InputError as error:
        print(f"Cannot read the folder: {error}")
        return 1

    detect_project_languages(project)
    validate_project(project)
    analyze_project(project)
    existing = validation_to_issues(project) + static_to_issues(project)

    print(f"Project: {project.project_name} ({project.file_count} files)")
    print(f"Provider: {provider.name}   Model: {provider.model}")
    print(f"Up to {args.max_files} files will be SENT to this service.")
    if not args.yes:
        if input("Send code to the AI service? [y/N] ").strip().lower() != "y":
            print("Cancelled. Nothing was sent.")
            return 0

    report = review_project(project, provider, existing, max_files=args.max_files)

    print(
        f"\nStatus: {report['status']}   Reviewed: {report['files_reviewed']}   "
        f"Failed: {report['files_failed']}   Skipped: {len(report['files_skipped'])}"
    )
    print(f"Findings kept: {report['finding_count']}   Dropped: {report['dropped']}")
    for item in report["file_errors"]:
        print(f"  error in {item['file_path']}: {item['message']}")
    for item in report["files_skipped"]:
        print(f"  skipped {item['file_path']}: {item['reason']}")

    for issue in ai_to_issues(project, report):
        print(f"\n{issue['file_path']}:{issue['line']} [{issue['severity']}/{issue['category']}] {issue['title']}")
        print(f"  {issue['explanation']}")
        if issue["suggestion"]:
            print(f"  Fix: {issue['suggestion']}")

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())