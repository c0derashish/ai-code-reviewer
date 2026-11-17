import os
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
TRUE_WORDS = ("1", "true", "yes", "on")
FALSE_WORDS = ("0", "false", "no", "off")


class SettingsError(Exception):
    """An API setting is wrong. The message says which one."""


@dataclass(frozen=True)
class Settings:
    allowed_origins: tuple = DEFAULT_ORIGINS
    max_body_bytes: int = 30 * 1024 * 1024  # one request: files, plus form overhead
    max_active_jobs: int = 4                 # analyses queued or running at the same time
    job_ttl_seconds: int = 3600              # a result is kept for 1 hour
    max_stored_jobs: int = 200
    ai_default_on: bool = False
    ai_max_files: int = 8
    ai_time_budget_seconds: int = 90
    docs_enabled: bool = True


def _origin(text) -> str:
    value = text.strip().rstrip("/")
    if value == "*":
        raise SettingsError(
            "VEDIX_ALLOWED_ORIGINS must list exact origins. '*' does not work with cookies."
        )
    parsed = urlparse(value)
    bad = (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    )
    if bad:
        raise SettingsError(
            f"VEDIX_ALLOWED_ORIGINS has a bad entry: {text!r}. Use origins like http://localhost:5173"
        )
    return value


def _flag(environ, name, default) -> bool:
    text = environ.get(name, "").strip().lower()
    if text == "":
        return default
    if text in TRUE_WORDS:
        return True
    if text in FALSE_WORDS:
        return False
    raise SettingsError(f"{name} must be true or false.")


def _number(environ, name, default, minimum=1) -> int:
    text = environ.get(name, "").strip()
    if text == "":
        return default
    try:
        value = int(text)
    except ValueError:
        raise SettingsError(f"{name} must be a whole number.") from None
    if value < minimum:
        raise SettingsError(f"{name} must be at least {minimum}.")
    return value


def load_settings(environ=None) -> Settings:
    environ = os.environ if environ is None else environ
    defaults = Settings()

    origins = defaults.allowed_origins
    text = environ.get("VEDIX_ALLOWED_ORIGINS", "").strip()
    if text:
        origins = tuple(_origin(part) for part in text.split(",") if part.strip())
        if not origins:
            raise SettingsError("VEDIX_ALLOWED_ORIGINS has no origin in it.")

    return Settings(
        allowed_origins=origins,
        max_active_jobs=_number(environ, "VEDIX_MAX_ACTIVE_JOBS", defaults.max_active_jobs),
        ai_default_on=_flag(environ, "VEDIX_API_AI_DEFAULT", defaults.ai_default_on),
        docs_enabled=_flag(environ, "VEDIX_API_DOCS", defaults.docs_enabled),
    )