import json
import time

import pytest
from fastapi.testclient import TestClient

from analyzer.static.integrations import tool_runner
from api import runner
from api.app import create_app
from api.jobs import JobStore
from api.settings import Settings, SettingsError, load_settings

ORIGIN = "http://localhost:5173"

CODE = "\n".join([
    "import os",
    "",
    "def run(user_input):",
    "    result = eval(user_input)",
    "    return result",
    "",
])


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def complete(self, system, user):
        self.calls.append(user)
        issue = {
            "line": 4, "code_quote": "result = eval(user_input)", "severity": "high",
            "category": "security", "title": "eval on user input",
            "explanation": "eval runs any code.", "confidence": "high",
        }
        return json.dumps({"issues": [issue]})


def make_client(provider=None, **changes):
    return TestClient(create_app(Settings(**changes), provider))


def upload(client, files, scope="project", headers=None, **fields):
    """POST /analyses the way the VEDIX frontend does: one 'paths' and one 'files' per file."""
    parts = [("project_name", (None, "demo")), ("scope", (None, scope))]
    for name, value in fields.items():
        parts.append((name, (None, value)))
    for path in files:
        parts.append(("paths", (None, path)))
    for path, text in files.items():
        parts.append(("files", (path.split("/")[-1], text.encode("utf-8"), "text/plain")))
    return client.post("/analyses", files=parts, headers=headers)


def wait_for(client, job_id):
    for _ in range(100):
        body = client.get(f"/analyses/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("the analysis did not finish")


def run(client, files, **options):
    response = upload(client, files, **options)
    assert response.status_code == 202, response.text
    return wait_for(client, response.json()["id"])


# ---------- basics ----------

def test_health():
    response = make_client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_only_the_vedix_origin():
    client = make_client()

    preflight = client.options(
        "/analyses",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ORIGIN
    assert preflight.headers["access-control-allow-credentials"] == "true"

    allowed = client.get("/health", headers={"Origin": ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN

    stranger = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in stranger.headers


# ---------- the analysis flow ----------

def test_full_flow_returns_vedix_issues():
    client = make_client()
    response = upload(client, {"bad.py": "def broken(:\n", "calc.py": CODE})

    assert response.status_code == 202
    started = response.json()
    assert set(started) == {"id", "status"}
    assert started["status"] == "queued"
    assert len(started["id"]) >= 16

    result = wait_for(client, started["id"])
    assert result["status"] == "done"
    assert result["id"] == started["id"]
    assert result["score"] is None
    assert result["error"] is None
    assert len(result["issues"]) == 1

    issue = result["issues"][0]
    assert set(issue) == {
        "id", "file_path", "line", "severity", "category", "title",
        "explanation", "suggestion", "before", "after", "source", "rule",
    }
    assert issue["file_path"] == "bad.py"
    assert issue["line"] == 1
    assert issue["severity"] == "high"
    assert issue["category"] == "bug"
    assert issue["title"] == "Syntax error"
    assert issue["before"] == "def broken(:"
    assert issue["suggestion"]
    assert issue["source"] == "validation"
    assert issue["rule"] is None
    assert issue["after"] is None

    assert result["summary"] == {
        "files": 2,
        "analyzed": 1,
        "not_analyzed": 1,
        "files_skipped": 0,
        "primary_language": "python",
        "issue_count": 1,
        "issues_truncated": False,
        "tools": {"ruff": "unavailable", "bandit": "unavailable"},
        "duplication": "ok",
        "ai": "not_used",
    }


def test_paths_come_back_exactly_as_sent():
    result = run(make_client(), {"my-project/src/app.py": "def broken(:\n"})
    assert result["issues"][0]["file_path"] == "my-project/src/app.py"


def test_scope_file_drops_warnings_about_missing_sibling_files():
    code = {"calc.py": "from .tools import x\n"}

    project_result = run(make_client(), code, scope="project")
    assert [issue["title"] for issue in project_result["issues"]] == ["Import cannot be resolved"]

    file_result = run(make_client(), code, scope="file")
    assert file_result["issues"] == []


# ---------- AI review ----------

def test_ai_review_only_when_asked():
    provider = FakeProvider()
    client = make_client(provider)

    result = run(client, {"calc.py": CODE})
    assert provider.calls == []
    assert result["issues"] == []
    assert result["summary"]["ai"] == "not_used"

    result = run(client, {"calc.py": CODE}, ai_review="true")
    assert len(provider.calls) == 1
    assert result["summary"]["ai"] == "ok"
    assert len(result["issues"]) == 1

    issue = result["issues"][0]
    assert issue["source"] == "ai"
    assert issue["rule"] == "ai_review"
    assert issue["line"] == 4
    assert issue["severity"] == "high"
    assert issue["category"] == "security"
    assert issue["before"] == "    result = eval(user_input)"
    assert issue["after"] is None
    assert "eval runs any code." in issue["explanation"]


def test_ai_default_setting_can_be_overridden_by_the_request():
    provider = FakeProvider()
    client = make_client(provider, ai_default_on=True)

    run(client, {"calc.py": CODE})
    assert len(provider.calls) == 1  # no field in the request, so the default (on) applies

    run(client, {"calc.py": CODE}, ai_review="false")
    assert len(provider.calls) == 1  # the request said no


def test_ai_requested_but_not_set_up_on_the_server():
    result = run(make_client(), {"calc.py": CODE}, ai_review="true")

    assert result["status"] == "done"
    assert result["issues"] == []
    assert result["summary"]["ai"] == "not_used"


# ---------- bad requests ----------

def test_bad_requests_get_a_text_message():
    client = make_client()

    empty = client.post("/analyses")
    assert empty.status_code == 422
    assert isinstance(empty.json()["detail"], str)

    wrong_scope = upload(client, {"a.py": "x = 1\n"}, scope="everything")
    assert wrong_scope.status_code == 422
    assert "scope" in wrong_scope.json()["detail"]

    mismatch = client.post("/analyses", files=[
        ("project_name", (None, "d")),
        ("scope", (None, "file")),
        ("paths", (None, "a.py")),
        ("paths", (None, "b.py")),
        ("files", ("a.py", b"x = 1\n", "text/plain")),
    ])
    assert mismatch.status_code == 422
    assert "one path for every file" in mismatch.json()["detail"]

    nothing_usable = upload(client, {"notes.txt": "hello"})
    assert nothing_usable.status_code == 422
    assert nothing_usable.json()["detail"].startswith("No supported source files found")


def test_unknown_analysis_is_404():
    response = make_client().get("/analyses/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found. It may have expired."


def test_busy_server_answers_429():
    client = make_client(max_active_jobs=1)
    store = client.app.state.store
    stuck = store.try_create(1)  # a job that never finishes

    response = upload(client, {"a.py": "x = 1\n"})
    assert response.status_code == 429
    assert "busy" in response.json()["detail"]

    store.finish(stuck.id, [], {})
    assert upload(client, {"a.py": "x = 1\n"}).status_code == 202


def test_too_large_upload_is_refused_with_cors_headers():
    client = make_client(max_body_bytes=2000)

    response = upload(client, {"a.py": "x = 1\n" * 1000}, headers={"Origin": ORIGIN})

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_too_large_upload_without_a_size_header_is_refused():
    client = make_client(max_body_bytes=2000)

    def chunks():
        for _ in range(10):
            yield b"x" * 500

    response = client.post(
        "/analyses",
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=x"},
    )

    assert response.status_code == 413


def test_repositories_are_not_available_yet():
    response = make_client().post("/repositories", json={"url": "https://github.com/a/b"})

    assert response.status_code == 400
    assert "not available yet" in response.json()["detail"]


def test_a_crash_is_reported_without_details(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(runner, "run_pipeline", broken)

    result = run(make_client(), {"a.py": "x = 1\n"})

    assert result["status"] == "failed"
    assert result["error"] == runner.FAILED_MESSAGE
    assert result["issues"] == []
    assert "secret detail" not in json.dumps(result)


def test_docs_can_be_switched_off():
    assert make_client().get("/docs").status_code == 200

    off = make_client(docs_enabled=False)
    assert off.get("/docs").status_code == 404
    assert off.get("/openapi.json").status_code == 404


# ---------- the job store and the settings ----------

def test_jobs_expire_and_copies_are_safe():
    now = [0.0]
    store = JobStore(ttl_seconds=100, max_jobs=10, clock=lambda: now[0])

    job = store.try_create(5)
    assert store.get(job.id).status == "queued"

    store.mark_running(job.id)
    assert store.get(job.id).status == "running"

    store.finish(job.id, [{"id": "x"}], {"files": 1})
    done = store.get(job.id)
    assert (done.status, done.issues, done.summary) == ("done", [{"id": "x"}], {"files": 1})

    done.status = "changed outside"
    assert store.get(job.id).status == "done"  # the store gave a copy

    other = store.try_create(5)
    store.fail(other.id, "boom")
    failed = store.get(other.id)
    assert (failed.status, failed.error) == ("failed", "boom")

    now[0] = 101.0
    assert store.get(job.id) is None


def test_job_store_limits():
    now = [0.0]
    store = JobStore(ttl_seconds=1000, max_jobs=2, clock=lambda: now[0])

    first = store.try_create(10)
    store.finish(first.id, [], {})
    now[0] = 1.0
    second = store.try_create(10)
    store.finish(second.id, [], {})
    now[0] = 2.0
    third = store.try_create(10)  # still queued

    assert store.get(first.id) is None   # the oldest finished job made room
    assert store.get(second.id) is not None
    assert store.get(third.id) is not None
    assert store.try_create(1) is None   # one job is still active


def test_settings_from_the_environment():
    assert load_settings({}) == Settings()

    settings = load_settings({
        "VEDIX_ALLOWED_ORIGINS": "http://localhost:3000, https://app.example.com/",
        "VEDIX_API_AI_DEFAULT": "yes",
        "VEDIX_API_DOCS": "off",
        "VEDIX_MAX_ACTIVE_JOBS": "2",
    })
    assert settings.allowed_origins == ("http://localhost:3000", "https://app.example.com")
    assert settings.ai_default_on is True
    assert settings.docs_enabled is False
    assert settings.max_active_jobs == 2

    bad_settings = [
        {"VEDIX_ALLOWED_ORIGINS": "*"},
        {"VEDIX_ALLOWED_ORIGINS": "http://x.com/path"},
        {"VEDIX_ALLOWED_ORIGINS": "localhost:5173"},
        {"VEDIX_API_AI_DEFAULT": "maybe"},
        {"VEDIX_MAX_ACTIVE_JOBS": "0"},
        {"VEDIX_MAX_ACTIVE_JOBS": "many"},
    ]
    for environ in bad_settings:
        with pytest.raises(SettingsError):
            load_settings(environ)