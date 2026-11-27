import re
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse

# Only these hosts are ever contacted, also after a redirect.
ALLOWED_HOSTS = ("github.com", "codeload.github.com")
REDIRECT_CODES = (301, 302, 303, 307, 308)
MAX_REDIRECTS = 3
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
DOWNLOAD_DEADLINE_SECONDS = 60
SOCKET_TIMEOUT_SECONDS = 20
CHUNK_BYTES = 64 * 1024
USER_AGENT = "VEDIX-repo-fetcher/0.1"

OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

MSG_EMPTY = "Enter a repository URL."
MSG_BAD = "The address is not valid."
MSG_ONLY_GITHUB = "Only https://github.com/owner/repository addresses are supported."
MSG_REMOVE = "Remove credentials, tokens and ?query parts from the address."
MSG_FORM = "The address must look like https://github.com/owner/repository"
MSG_NAMES = "The owner or repository name has characters GitHub does not allow."
MSG_REDIRECT = "GitHub redirected to an address we do not follow."


class FetchError(Exception):
    """The repository could not be fetched. The message is safe to show to a user."""


def parse_github_url(text):
    """Returns (owner, repo) for https://github.com/owner/repo. Raises FetchError."""
    if not isinstance(text, str) or text.strip() == "":
        raise FetchError(MSG_EMPTY)

    try:
        url = urlparse(text.strip())
        port = url.port
    except ValueError:
        raise FetchError(MSG_BAD) from None

    if url.scheme != "https" or url.hostname != "github.com":
        raise FetchError(MSG_ONLY_GITHUB)
    if url.username or url.password or url.query or url.fragment or url.params:
        raise FetchError(MSG_REMOVE)
    if port not in (None, 443):
        raise FetchError(MSG_BAD)

    parts = [part for part in url.path.split("/") if part]
    if len(parts) != 2:
        raise FetchError(MSG_FORM)

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]

    # "." and ".." match the pattern, so they are refused by name
    if not OWNER_PATTERN.match(owner) or not REPO_PATTERN.match(repo) or repo in (".", ".."):
        raise FetchError(MSG_NAMES)
    return owner, repo


def archive_url(owner, repo) -> str:
    """The default branch as a ZIP file."""
    return f"https://github.com/{owner}/{repo}/archive/HEAD.zip"


def _describe_size(size) -> str:
    megabytes = size / (1024 * 1024)
    if megabytes >= 1:
        return f"{megabytes:.0f} MB"
    return f"{max(1, size // 1024)} KB"


def _message_for_status(status) -> str:
    if status == 404:
        return "Repository not found. It may not exist, or it may be private. Only public repositories work."
    if status in (403, 429):
        return "GitHub is limiting requests right now. Try again later."
    if status == 451:
        return "GitHub cannot serve this repository (blocked for legal reasons)."
    if status >= 500:
        return "GitHub had a problem. Try again later."
    return f"GitHub answered with status {status}."


def _check_allowed(url):
    """Refuse any address that is not https on an allowed host."""
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        raise FetchError(MSG_REDIRECT) from None

    allowed = (
        parsed.scheme == "https"
        and parsed.hostname in ALLOWED_HOSTS
        and not parsed.username
        and not parsed.password
        and port in (None, 443)
    )
    if not allowed:
        raise FetchError(MSG_REDIRECT)


def _header(headers, name):
    """Header value, whatever the capital letters of the name."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """We follow redirects ourselves, so that every target is checked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def default_open_url(url):
    """One request. Returns (status, headers, stream). stream is None for errors and redirects."""
    # the licence question goes to GitHub's API and wants JSON. The archive wants a ZIP
    wants_json = url.startswith("https://api.github.com/")
    accept = "application/vnd.github+json" if wants_json else "application/zip, application/octet-stream"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        response = _OPENER.open(request, timeout=SOCKET_TIMEOUT_SECONDS)
    except urllib.error.HTTPError as error:
        status, headers = error.code, dict(error.headers.items())
        error.close()
        return status, headers, None
    except OSError:
        raise FetchError("Cannot reach GitHub.") from None
    return response.status, dict(response.headers.items()), response


def _read_body(stream, headers, max_bytes, deadline):
    chunks = []
    total = 0
    try:
        length = _header(headers, "Content-Length")
        if length is not None and length.isdigit() and int(length) > max_bytes:
            raise FetchError(f"The repository download is larger than {_describe_size(max_bytes)}.")

        while True:
            if time.monotonic() >= deadline:
                raise FetchError("GitHub took too long to send the repository.")
            chunk = stream.read(CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise FetchError(f"The repository download is larger than {_describe_size(max_bytes)}.")
            chunks.append(chunk)
    except OSError:
        raise FetchError("The download was interrupted.") from None
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
    return b"".join(chunks)


def fetch_archive(
    owner, repo, open_url=None, max_bytes=MAX_DOWNLOAD_BYTES, deadline_seconds=DOWNLOAD_DEADLINE_SECONDS
) -> bytes:
    """Download the ZIP of a public repository. Raises FetchError.

    open_url(url) -> (status, headers, stream). Tests give a fake one.
    """
    open_url = open_url or default_open_url
    deadline = time.monotonic() + deadline_seconds
    url = archive_url(owner, repo)

    for _ in range(MAX_REDIRECTS + 1):
        _check_allowed(url)
        status, headers, stream = open_url(url)

        if status in REDIRECT_CODES:
            location = _header(headers, "Location")
            if not location:
                raise FetchError("GitHub sent a redirect without an address.")
            url = urljoin(url, location)
            continue

        if status == 200:
            return _read_body(stream, headers, max_bytes, deadline)
        raise FetchError(_message_for_status(status))

    raise FetchError("GitHub redirected too many times.")