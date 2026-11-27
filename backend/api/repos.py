import secrets
import threading
import time
from dataclasses import dataclass, replace

ACTIVE = ("queued", "running")
FINISHED = ("done", "failed")


@dataclass
class RepoEntry:
    id: str
    owner: str = ""
    repo: str = ""
    status: str = "queued"
    created: float = 0.0
    project: object | None = None  # a CodeProject when done
    error: str | None = None
    licence: dict | None = None  # what GitHub says about the licence


class RepoStore:
    """Fetched repositories, in memory only. Lost on restart. Same idea as JobStore.

    Each entry can hold up to about 25 MB of source text, so the number of entries is small.
    """

    def __init__(self, ttl_seconds=1800, max_entries=5, clock=time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._entries = {}
        self._lock = threading.Lock()

    def _prune(self):
        """Drop old entries. The caller holds the lock."""
        now = self._clock()
        for entry_id in [i for i, e in self._entries.items() if now - e.created > self._ttl]:
            del self._entries[entry_id]

        extra = len(self._entries) - self._max
        if extra > 0:
            finished = sorted(
                (e for e in self._entries.values() if e.status in FINISHED), key=lambda e: e.created
            )
            for entry in finished[:extra]:
                del self._entries[entry.id]

    def try_create(self, max_active, owner, repo):
        """A new queued entry, or None when max_active fetches are already running."""
        with self._lock:
            self._prune()
            active = sum(1 for e in self._entries.values() if e.status in ACTIVE)
            if active >= max_active:
                return None
            entry = RepoEntry(id=secrets.token_urlsafe(16), owner=owner, repo=repo, created=self._clock())
            self._entries[entry.id] = entry
            return replace(entry)

    def get(self, entry_id):
        with self._lock:
            self._prune()
            entry = self._entries.get(entry_id)
            return replace(entry) if entry else None

    def mark_running(self, entry_id):
        with self._lock:
            if entry_id in self._entries:
                self._entries[entry_id].status = "running"

    def finish(self, entry_id, project, licence=None):
        with self._lock:
            if entry_id in self._entries:
                self._entries[entry_id].status = "done"
                self._entries[entry_id].project = project
                self._entries[entry_id].licence = licence

    def fail(self, entry_id, message):
        with self._lock:
            if entry_id in self._entries:
                self._entries[entry_id].status = "failed"
                self._entries[entry_id].error = message