import re
import threading
import time

from fastapi import HTTPException

COOKIE_NAME = "vedix_session"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------- checks (the same rules as the frontend) ----------

def check_name(text):
    value = text.strip()
    if value == "":
        return "Enter your name."
    if len(value) > 60:
        return "Use 60 characters or fewer."
    return None


def check_email(text):
    value = text.strip()
    if value == "":
        return "Enter your email."
    if len(value) > 254 or not EMAIL_PATTERN.match(value):
        return "Enter a valid email, like name@example.com."
    return None


def check_password(text):
    if text == "":
        return "Enter a password."
    if len(text) < 8:
        return "Use at least 8 characters."
    if len(text) > 128:
        return "Use 128 characters or fewer."
    return None


# ---------- the cookie ----------

def set_session_cookie(response, token, settings):
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,  # JavaScript on the page cannot read it
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_session_cookie(response, settings):
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def check_origin(request, allowed_origins):
    """A browser always names the page a request comes from. Refuse unknown pages.
    A request with no Origin header (curl, tools) is let through."""
    origin = request.headers.get("origin")
    if origin and origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="This request came from an address that is not allowed.")


def client_ip(request) -> str:
    # Behind a proxy this is the proxy's address. Handle that before a public deployment.
    return request.client.host if request.client else "unknown"


class LoginLimiter:
    """Counts failed sign-ins in memory. Lost on restart, and not shared between server processes."""

    def __init__(self, max_failures=5, window_seconds=900, max_keys=10000, clock=time.monotonic):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._failures = {}
        self._lock = threading.Lock()

    def _recent(self, key):
        now = self._clock()
        times = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
        if times:
            self._failures[key] = times
        else:
            self._failures.pop(key, None)
        return times

    def blocked(self, key) -> bool:
        with self._lock:
            return len(self._recent(key)) >= self.max_failures

    def record_failure(self, key):
        with self._lock:
            if key not in self._failures and len(self._failures) >= self.max_keys:
                self._failures.pop(next(iter(self._failures)))  # drop the oldest key
            self._failures.setdefault(key, []).append(self._clock())

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)