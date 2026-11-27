import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from analyzer.static.integrations import tool_runner
from api.app import create_app
from api.repo_runner import FAILED_MESSAGE
from api.repos import RepoStore
from api.settings import Settings, SettingsError, load_settings

ORIGIN = "http://localhost:5173"
URL = "https://github.com/octocat/Hello-World"


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name, content in files.items():
            target.writestr(name, content)
    return buffer.getvalue()


MIT_ANSWER = json.dumps(
    {"license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"}}
).encode("utf-8")


def fake_github(zip_bytes, licence=(200, MIT_ANSWER)):
    """Acts like GitHub: a redirect first, then the archive. The licence answer is `licence`."""
    def open_url(url):
        if url.startswith("https://api.github.com/"):
            status, body = licence
            return status, {}, (io.BytesIO(body) if status == 200 else None)
        if url.startswith("https://github.com/"):
            return 302, {"Location": "https://codeload.github.com/octocat/Hello-World/zip/HEAD"}, None
        return 200, {"Content-Length": str(len(zip_bytes))}, io.BytesIO(zip_bytes)
    return open_url


def make_client(open_url=None, **changes):
    return TestClient(create_app(Settings(**changes), None, open_url))


def wait_for(client, path):
    for _ in range(100):
        body = client.get(path).json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("it did not finish")


ZIP = make_zip({
    "Hello-World-HEAD/src/app.py": "x = 1\n",
    "Hello-World-HEAD/index.js": "var a = 1;\n",
    "Hello-World-HEAD/README.md": "# hi\n",
})


def test_fetch_and_read_a_repository():
    client = make_client(fake_github(ZIP))

    response = client.post("/repositories", json={"url": URL})
    assert response.status_code == 202
    started = response.json()
    assert set(started) == {"id", "status"}
    assert started["status"] == "queued"

    status = wait_for(client, f"/repositories/{started['id']}")
    assert status == {
        "id": started["id"], "status": "done", "project_name": "Hello-World",
        "file_count": 2, "skipped_count": 1, "error": None,
        "licence": {"status": "found", "spdx_id": "MIT", "name": "MIT License"},
        "storage": "full",
        "storage_reason": "Licence MIT is on our list of open licences, so the code is saved.",
    }

    files = client.get(f"/repositories/{started['id']}/files")
    assert files.status_code == 200
    assert files.json() == {
        "project_name": "Hello-World",
        "files": [
            {"path": "index.js", "language": "javascript", "content": "var a = 1;\n"},
            {"path": "src/app.py", "language": "python", "content": "x = 1\n"},
        ],
    }


def test_fetched_files_can_be_analysed():
    zip_bytes = make_zip({"r-HEAD/bad.py": "def broken(:\n", "r-HEAD/ok.py": "x = 1\n"})
    client = make_client(fake_github(zip_bytes))
    started = client.post("/repositories", json={"url": URL}).json()
    wait_for(client, f"/repositories/{started['id']}")
    fetched = client.get(f"/repositories/{started['id']}/files").json()["files"]

    # what the frontend does next: send the files to the analysis endpoint
    parts = [("project_name", (None, "demo")), ("scope", (None, "project"))]
    parts += [("paths", (None, item["path"])) for item in fetched]
    parts += [("files", (item["path"], item["content"].encode("utf-8"), "text/plain")) for item in fetched]
    analysis = client.post("/analyses", files=parts)
    assert analysis.status_code == 202

    result = wait_for(client, f"/analyses/{analysis.json()['id']}")
    assert result["status"] == "done"
    assert [(i["file_path"], i["title"]) for i in result["issues"]] == [("bad.py", "Syntax error")]


def test_invalid_address_is_refused():
    client = make_client(fake_github(ZIP))

    response = client.post("/repositories", json={"url": "https://gitlab.com/a/b"})

    assert response.status_code == 422
    assert "Only https" in response.json()["detail"]


def test_bad_body_is_refused():
    client = make_client(fake_github(ZIP))

    response = client.post("/repositories", json={"nope": 1})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "url" in response.json()["detail"]


def test_github_404_is_reported():
    client = make_client(lambda url: (404, {}, None))
    started = client.post("/repositories", json={"url": URL}).json()

    status = wait_for(client, f"/repositories/{started['id']}")

    assert status["status"] == "failed"
    assert "not found" in status["error"]
    assert status["project_name"] is None
    files = client.get(f"/repositories/{started['id']}/files")
    assert files.status_code == 409
    assert "not found" in files.json()["detail"]


def test_unknown_repository_is_404():
    client = make_client()

    assert client.get("/repositories/nope").status_code == 404
    assert client.get("/repositories/nope/files").status_code == 404


def test_files_before_the_fetch_is_done():
    client = make_client()
    entry = client.app.state.repos.try_create(5, "a", "b")  # stays queued

    response = client.get(f"/repositories/{entry.id}/files")

    assert response.status_code == 409
    assert "not ready yet" in response.json()["detail"]


def test_busy_server_answers_429():
    client = make_client(fake_github(ZIP), max_active_fetches=1)
    client.app.state.repos.try_create(1, "a", "b")  # a fetch that never ends

    response = client.post("/repositories", json={"url": URL})

    assert response.status_code == 429
    assert "busy" in response.json()["detail"]


def test_fetching_can_be_switched_off():
    client = make_client(fake_github(ZIP), repos_enabled=False)

    response = client.post("/repositories", json={"url": URL})

    assert response.status_code == 400
    assert "switched off" in response.json()["detail"]


def test_a_crash_is_reported_without_details():
    def broken(url):
        raise RuntimeError("secret detail")

    client = make_client(broken)
    started = client.post("/repositories", json={"url": URL}).json()

    status = wait_for(client, f"/repositories/{started['id']}")

    assert status["status"] == "failed"
    assert status["error"] == FAILED_MESSAGE
    assert "secret detail" not in json.dumps(status)


def test_repo_store_expiry_and_limits():
    now = [0.0]
    store = RepoStore(ttl_seconds=100, max_entries=2, clock=lambda: now[0])

    first = store.try_create(5, "o", "a")
    store.finish(first.id, "project-a")
    now[0] = 1.0
    second = store.try_create(5, "o", "b")
    store.finish(second.id, "project-b")
    now[0] = 2.0
    third = store.try_create(5, "o", "c")  # still queued

    assert store.get(first.id) is None  # the oldest finished entry made room
    assert store.get(second.id).project == "project-b"
    assert store.get(third.id).status == "queued"
    assert store.try_create(1, "o", "d") is None  # one fetch is still active

    store.mark_running(third.id)
    assert store.get(third.id).status == "running"
    store.fail(third.id, "boom")
    failed = store.get(third.id)
    assert (failed.status, failed.error) == ("failed", "boom")

    now[0] = 200.0
    assert store.get(second.id) is None  # older than the time limit


def test_settings_for_repositories():
    assert load_settings({}) == Settings()
    assert Settings().repos_enabled is True

    settings = load_settings({"VEDIX_API_REPOS": "off", "VEDIX_MAX_ACTIVE_FETCHES": "3"})
    assert settings.repos_enabled is False
    assert settings.max_active_fetches == 3

    for bad in [{"VEDIX_API_REPOS": "maybe"}, {"VEDIX_MAX_ACTIVE_FETCHES": "0"}]:
        with pytest.raises(SettingsError):
            load_settings(bad)


def test_cors_preflight_for_repositories():
    client = make_client()

    response = client.options(
        "/repositories",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN