import json

from repo_fetcher.github import FetchError, default_open_url

LICENCE_URL = "https://api.github.com/repos/{owner}/{repo}/license"
MAX_LICENCE_BYTES = 256 * 1024


def _result(status, spdx_id=None, name=None) -> dict:
    return {"status": status, "spdx_id": spdx_id, "name": name}


def fetch_licence(owner, repo, open_url=None) -> dict:
    """Ask GitHub which licence a public repository has. Never raises.

    status "found": spdx_id may be "NOASSERTION" when GitHub does not recognise the licence.
    status "none":  GitHub found no licence file.
    status "error": we could not find out (rate limit, outage, odd answer).
    GitHub says its detection is not legal advice.
    owner and repo must already have passed parse_github_url().
    """
    open_url = open_url or default_open_url
    url = LICENCE_URL.format(owner=owner, repo=repo)

    try:
        status, headers, stream = open_url(url)
    except (FetchError, OSError):
        return _result("error")

    try:
        if status == 404:
            return _result("none")
        if status != 200 or stream is None:
            return _result("error")
        raw = stream.read(MAX_LICENCE_BYTES + 1)
    except OSError:
        return _result("error")
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()

    if len(raw) > MAX_LICENCE_BYTES:
        return _result("error")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _result("error")

    if not isinstance(data, dict) or "license" not in data:
        return _result("error")
    licence = data["license"]
    if licence is None:
        return _result("none")
    if not isinstance(licence, dict):
        return _result("error")

    spdx_id, name = licence.get("spdx_id"), licence.get("name")
    return _result(
        "found",
        spdx_id[:50] if isinstance(spdx_id, str) else None,
        name[:100] if isinstance(name, str) else None,
    )