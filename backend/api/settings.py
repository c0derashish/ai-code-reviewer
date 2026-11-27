import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
TRUE_WORDS = ("1", "true", "yes", "on")
FALSE_WORDS = ("0", "false", "no", "off")
DB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,38}$")
SAMESITE_VALUES = ("lax", "strict", "none")


class SettingsError(Exception):
    """An API setting is wrong. The message says which one. It never contains a secret."""


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
    repos_enabled: bool = True               # fetch public GitHub repositories
    max_active_fetches: int = 2              # repository downloads at the same time
    repo_ttl_seconds: int = 1800             # a fetched repository is kept for 30 minutes
    max_stored_repos: int = 5                # each can hold up to about 25 MB in memory
    mongo_uri: str = field(default="", repr=False)  # can hold a password: never printed
    mongo_db: str = "vedix"
    cookie_secure: bool = False              # true when the site runs on https
    cookie_samesite: str = "lax"
    session_days: int = 7


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


def _mongo_uri(text) -> str:
    value = text.strip()
    if value == "":
        return ""
    starts_right = value.startswith("mongodb://") or value.startswith("mongodb+srv://")
    if not starts_right or any(char.isspace() for char in value):
        # the value is not repeated here: it can contain a password
        raise SettingsError("MONGODB_URI must start with mongodb:// or mongodb+srv:// and have no spaces.")
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

    mongo_db = environ.get("MONGODB_DB", "").strip() or defaults.mongo_db
    if not DB_NAME_PATTERN.match(mongo_db):
        raise SettingsError("MONGODB_DB may only use letters, digits, _ and -.")

    secure = _flag(environ, "VEDIX_COOKIE_SECURE", defaults.cookie_secure)
    samesite = environ.get("VEDIX_COOKIE_SAMESITE", "").strip().lower() or defaults.cookie_samesite
    if samesite not in SAMESITE_VALUES:
        raise SettingsError("VEDIX_COOKIE_SAMESITE must be lax, strict or none.")
    if samesite == "none" and not secure:
        raise SettingsError("VEDIX_COOKIE_SAMESITE=none needs VEDIX_COOKIE_SECURE=true.")

    return Settings(
        allowed_origins=origins,
        max_active_jobs=_number(environ, "VEDIX_MAX_ACTIVE_JOBS", defaults.max_active_jobs),
        ai_default_on=_flag(environ, "VEDIX_API_AI_DEFAULT", defaults.ai_default_on),
        docs_enabled=_flag(environ, "VEDIX_API_DOCS", defaults.docs_enabled),
        repos_enabled=_flag(environ, "VEDIX_API_REPOS", defaults.repos_enabled),
        max_active_fetches=_number(environ, "VEDIX_MAX_ACTIVE_FETCHES", defaults.max_active_fetches),
        mongo_uri=_mongo_uri(environ.get("MONGODB_URI", "")),
        mongo_db=mongo_db,
        cookie_secure=secure,
        cookie_samesite=samesite,
        session_days=_number(environ, "VEDIX_SESSION_DAYS", defaults.session_days),
    )