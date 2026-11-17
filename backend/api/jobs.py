import secrets
import threading
import time
from dataclasses import dataclass, field, replace

ACTIVE = ("queued", "running")
FINISHED = ("done", "failed")


@dataclass
class Job:
    id: str
    status: str = "queued"
    created: float = 0.0
    issues: list = field(default_factory=list)
    summary: dict | None = None
    error: str | None = None


class JobStore:
    """Keeps analysis jobs in memory. Lost when the server restarts.

    A job id is long and random. Anyone who knows the id can read the result,
    so there is no login to protect. Do not put this on the open internet yet.
    """

    def __init__(self, ttl_seconds=3600, max_jobs=200, clock=time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_jobs
        self._clock = clock
        self._jobs = {}
        self._lock = threading.Lock()

    def _prune(self):
        """Remove old jobs. The caller holds the lock."""
        now = self._clock()
        for job_id in [i for i, job in self._jobs.items() if now - job.created > self._ttl]:
            del self._jobs[job_id]

        extra = len(self._jobs) - self._max
        if extra > 0:
            finished = sorted(
                (job for job in self._jobs.values() if job.status in FINISHED),
                key=lambda job: job.created,
            )
            for job in finished[:extra]:
                del self._jobs[job.id]

    def try_create(self, max_active):
        """A new queued job, or None when max_active jobs are already running."""
        with self._lock:
            self._prune()
            active = sum(1 for job in self._jobs.values() if job.status in ACTIVE)
            if active >= max_active:
                return None
            job = Job(id=secrets.token_urlsafe(16), created=self._clock())
            self._jobs[job.id] = job
            return replace(job)

    def get(self, job_id):
        """A copy of the job, or None if it is unknown or expired."""
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            return replace(job) if job else None

    def mark_running(self, job_id):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = "running"

    def finish(self, job_id, issues, summary):
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "done"
                job.issues = issues
                job.summary = summary

    def fail(self, job_id, message):
        with self._lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = "failed"
                job.error = message