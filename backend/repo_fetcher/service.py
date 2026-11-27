from repo_fetcher.archive import project_from_zip
from repo_fetcher.github import fetch_archive


def fetch_repository(owner, repo, open_url=None):
    """Download a public repository and return it as a CodeProject. Raises FetchError."""
    data = fetch_archive(owner, repo, open_url)
    return project_from_zip(data, repo)