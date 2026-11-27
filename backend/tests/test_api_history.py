import io
import time
import zipfile

import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from analyzer.static.integrations import tool_runner
from api import runner
from api.app import create_app
from api.settings import Settings
from app_db.clock import utc_now

EVIL = {"Origin": "http://evil.example"}
FILES = {"bad.py": "def broken(:\n", "ok.py": "x = 1\n"}
MIT_ANSWER = b'{"license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"}}'


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name, content in files.items():
            target.writestr(name, content)
    return buffer.getvalue()


REPO_ZIP = make_zip({"Hello-World-HEAD/bad.py": "def broken(:\n", "Hello-World-HEAD/ok.py": "x = 1\n"})


def fake_github(licence):
    """Acts like GitHub. licence is (status, body) for the licence question."""
    def open_url(url):
        if url.startswith("https://api.github.com/"):
            status, body = licence
            return status, {}, (io.BytesIO(body) if status == 200 else None)
        if url.startswith("https://github.com/"):
            return 302, {"Location": "https://codeload.github.com/octocat/Hello-World/zip/HEAD"}, None
        return 200, {"Content-Length": str(len(REPO_ZIP))}, io.BytesIO(REPO_ZIP)
    return open_url


def make_app(**options):
    database = mongomock.MongoClient().vedix
    return create_app(Settings(), database=database, **options), database


def register(client, email="ashish@example.com"):
    response = client.post(
        "/auth/register", json={"name": "Ashish", "email": email, "password": "correct horse"}
    )
    assert response.status_code == 201
    return response


def upload(client, files, headers=None, **fields):
    parts = [("project_name", (None, "demo")), ("scope", (None, "project"))]
    parts += [(name, (None, value)) for name, value in fields.items()]
    parts += [("paths", (None, path)) for path in files]
    parts += [("files", (path.split("/")[-1], text.encode("utf-8"), "text/plain")) for path, text in files.items()]
    return client.post("/analyses", files=parts, headers=headers)


def wait_for(client, path):
    for _ in range(100):
        body = client.get(path).json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("it did not finish")


def run(client, files=FILES, **fields):
    response = upload(client, files, **fields)
    assert response.status_code == 202, response.text
    return wait_for(client, f"/analyses/{response.json()['id']}")


def analyse_repository(client, licence_answer_ignored=None):
    """Fetch the fake repository, then analyse its files the way the frontend does."""
    started = client.post("/repositories", json={"url": "https://github.com/octocat/Hello-World"}).json()
    wait_for(client, f"/repositories/{started['id']}")
    fetched = client.get(f"/repositories/{started['id']}/files").json()["files"]
    files = {item["path"]: item["content"] for item in fetched}
    return run(client, files, repo_id=started["id"])


# ---------- saving and reading ----------

def test_a_signed_in_analysis_is_saved_and_can_be_read_again():
    app, db = make_app()
    client = TestClient(app)
    register(client)

    result = run(client)
    assert result["status"] == "done"
    assert result["summary"]["saved"] is True
    saved_id = result["summary"]["saved_analysis_id"]

    history = client.get("/history").json()
    assert len(history) == 1
    item = history[0]
    assert item["id"] == saved_id
    assert (item["project_name"], item["source"], item["storage"]) == ("demo", "upload", "full")
    assert (item["files"], item["files_analyzed"], item["loc"], item["issue_count"]) == (2, 1, 1, 1)
    assert item["primary_language"] == "python"
    assert item["severity_counts"]["high"] == 1
    assert item["status"] == "done"

    detail = client.get(f"/history/{saved_id}").json()
    assert detail["issues_stored"] is True
    assert [issue["title"] for issue in detail["issues"]] == ["Syntax error"]
    assert detail["issues"][0]["file_path"] == "bad.py"

    files = client.get(f"/history/{saved_id}/files").json()
    assert files["project_name"] == "demo"
    assert [(f["path"], f["language"], f["content"]) for f in files["files"]] == [
        ("bad.py", "python", "def broken(:\n"), ("ok.py", "python", "x = 1\n")]

    assert client.delete(f"/history/{saved_id}").status_code == 204
    assert client.get("/history").json() == []
    assert client.get(f"/history/{saved_id}").status_code == 404
    assert db["blobs"].count_documents({}) == 0


def test_signed_out_and_opted_out_analyses_are_not_saved():
    app, db = make_app()
    client = TestClient(app)

    result = run(client)  # signed out
    assert "saved_analysis_id" not in result["summary"]
    assert db["analyses"].count_documents({}) == 0

    register(client)
    result = run(client, save="false")
    assert "saved_analysis_id" not in result["summary"]
    assert db["analyses"].count_documents({}) == 0

    run(client)  # signed in and nothing said: saved
    assert db["analyses"].count_documents({}) == 1


def test_a_licensed_repository_is_saved_in_full():
    app, db = make_app(open_url=fake_github((200, MIT_ANSWER)))
    client = TestClient(app)
    register(client)

    result = analyse_repository(client)

    item = client.get("/history").json()[0]
    assert item["id"] == result["summary"]["saved_analysis_id"]
    assert (item["source"], item["storage"]) == ("github", "full")
    assert item["project_name"] == "octocat/Hello-World"
    assert item["repo_url"] == "https://github.com/octocat/Hello-World"
    assert item["licence"]["spdx_id"] == "MIT"
    detail = client.get(f"/history/{item['id']}").json()
    assert detail["issues_stored"] is True and len(detail["issues"]) == 1
    assert client.get(f"/history/{item['id']}/files").status_code == 200


def test_an_unlicensed_repository_is_saved_in_full():
    app, db = make_app(open_url=fake_github((404, b"")))
    client = TestClient(app)
    register(client)

    analyse_repository(client)

    item = client.get("/history").json()[0]
    assert (item["source"], item["storage"]) == ("github", "full")
    assert item["repo_url"] == "https://github.com/octocat/Hello-World"
    assert item["issue_count"] == 1  # the counts are kept
    detail = client.get(f"/history/{item['id']}").json()
    assert (detail["issues"], detail["issues_stored"]) == ([], False)

    files = client.get(f"/history/{item['id']}/files")
    assert files.status_code == 409
    assert "only the link" in files.json()["detail"]

    assert db["analysis_issues"].count_documents({}) == 0
    assert db["blobs"].count_documents({}) == 0
    assert "def broken" not in str(list(db["analyses"].find()))


def test_an_expired_repository_id_is_refused():
    app, db = make_app()
    client = TestClient(app)

    assert run(client, repo_id="nope")["status"] == "done"  # signed out: no saving, nothing to refuse

    register(client)
    response = upload(client, FILES, repo_id="nope")
    assert response.status_code == 422
    assert "expired" in response.json()["detail"]
    assert db["analyses"].count_documents({}) == 0


# ---------- who may see what ----------

def test_history_is_private():
    app, db = make_app()
    owner, stranger, nobody = TestClient(app), TestClient(app), TestClient(app)
    register(owner)
    register(stranger, email="other@example.com")
    saved_id = run(owner)["summary"]["saved_analysis_id"]

    assert nobody.get("/history").status_code == 401
    assert nobody.get("/history").json()["detail"] == "Please sign in."
    assert nobody.get("/analytics").status_code == 401

    assert stranger.get("/history").json() == []
    assert stranger.get(f"/history/{saved_id}").status_code == 404
    assert stranger.get(f"/history/{saved_id}/files").status_code == 404
    assert stranger.delete(f"/history/{saved_id}").status_code == 404
    assert len(owner.get("/history").json()) == 1


def test_the_origin_is_checked_when_saving_or_deleting():
    app, db = make_app()
    client = TestClient(app)
    register(client)
    saved_id = run(client)["summary"]["saved_analysis_id"]

    assert upload(client, FILES, headers=EVIL).status_code == 403
    assert client.delete(f"/history/{saved_id}", headers=EVIL).status_code == 403
    assert client.get("/history", headers=EVIL).status_code == 200  # reading is not a risk
    assert db["analyses"].count_documents({}) == 1

    signed_out = TestClient(app)  # no cookie came with this request, so there is nothing to protect
    assert upload(signed_out, FILES, headers=EVIL).status_code == 202


def test_a_failed_save_does_not_lose_the_result(monkeypatch):
    def broken(*args, **kwargs):
        raise PyMongoError("down")

    monkeypatch.setattr(runner.history_db, "save_analysis", broken)
    app, db = make_app()
    client = TestClient(app)
    register(client)

    result = run(client)

    assert result["status"] == "done"
    assert [issue["title"] for issue in result["issues"]] == ["Syntax error"]
    assert result["summary"]["saved"] is False
    assert "could not be saved" in result["summary"]["save_error"]
    assert db["analyses"].count_documents({}) == 0


def test_without_a_database_history_is_off_but_analysis_works():
    client = TestClient(create_app(Settings()))

    for path in ("/history", "/analytics"):
        response = client.get(path)
        assert response.status_code == 400
        assert "not set up" in response.json()["detail"]

    result = run(client)
    assert result["status"] == "done"
    assert "saved_analysis_id" not in result["summary"]


def test_analytics_from_the_api():
    app, db = make_app()
    client = TestClient(app)
    register(client)
    run(client)
    run(client)  # the same project again

    result = client.get("/analytics").json()

    assert result["totals"] == {
        "projects": 1, "analyses": 2, "files_analyzed": 1, "loc": 1,
        "issue_count": 1, "rule_issue_count": 1, "issues_per_100_loc": 100.0,
    }
    assert result["severity"]["high"] == 1
    assert result["languages"] == [{"language": "python", "lines": 2}]
    assert result["trend"] == [
        {"month": utc_now().strftime("%Y-%m"), "analyses": 2, "issues_per_100_loc": 100.0}]
    assert [(p["project_name"], p["analyses"]) for p in result["projects"]] == [("demo", 2)]
    assert result["truncated"] is False