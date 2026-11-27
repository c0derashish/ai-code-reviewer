import logging

from repo_fetcher.github import FetchError
from repo_fetcher.licence import fetch_licence
from repo_fetcher.service import fetch_repository

log = logging.getLogger("vedix.api")

FAILED_MESSAGE = "The repository could not be fetched because of a server problem."


def run_fetch(store, entry_id, owner, repo, open_url):
    """Runs in a background thread. Never raises."""
    store.mark_running(entry_id)
    try:
        project = fetch_repository(owner, repo, open_url)
        licence = fetch_licence(owner, repo, open_url)  # never raises: failures become status "error"
    except FetchError as error:
        store.fail(entry_id, str(error))  # these messages are written to be shown
        return
    except Exception:  # a crash must end as "failed", never as a fetch stuck on "running"
        log.exception("Repository fetch %s crashed.", entry_id[:8])
        store.fail(entry_id, FAILED_MESSAGE)
        return
    store.finish(entry_id, project, licence)