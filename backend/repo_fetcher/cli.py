"""Fetch a public GitHub repository and print what was found.

Usage:  python -m repo_fetcher.cli https://github.com/owner/repository
Nothing is saved to disk. Nothing from the repository is run.
"""
import argparse
from collections import Counter

from analyzer.languages import detect_project_languages
from repo_fetcher.github import FetchError, parse_github_url
from repo_fetcher.service import fetch_repository


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch a public GitHub repository.")
    parser.add_argument("url")
    args = parser.parse_args(argv)

    try:
        owner, repo = parse_github_url(args.url)
        project = fetch_repository(owner, repo)
    except FetchError as error:
        print(f"Cannot fetch: {error}")
        return 1

    summary = detect_project_languages(project)
    print(f"Repository: {owner}/{repo}")
    print(f"Source files: {project.file_count}   skipped: {project.skipped_count}")
    for info in summary["languages"].values():
        print(f"  {info['name']:<12} files {info['files']:>4}  lines {info['lines']:>6}  {info['percentage']}%")

    reasons = Counter(item.reason for item in project.skipped)
    if reasons:
        print("Skipped (the first 200 are listed):")
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}")

    print("\nA public repository is not free to reuse. Check its licence before using it as research data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())