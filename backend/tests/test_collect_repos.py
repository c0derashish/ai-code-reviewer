import csv
import io
import json
import os
import zipfile

import pytest

from analyzer.static.integrations import tool_runner
from data_science import collect
from data_science.collect import LOG_NAME, read_repo_list
from data_science.store import ResearchStore
from input_manager.models import CodeProject
from repo_fetcher.archive import project_from_zip

HEADER = "url,licence,checked_by,checked_on,ai_ok,note\n"


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


def make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name, content in files.items():
            target.writestr(name, content)
    return buffer.getvalue()


ZIP = make_zip({"r-HEAD/app.py": "x = 1\n", "r-HEAD/bad.py": "def broken(:\n"})


def fake_github(zip_bytes=ZIP, missing=()):
    """Acts like GitHub. Repositories named in `missing` answer 404."""
    def open_url(url):
        if any(f"/{name}/" in url for name in missing):
            return 404, {}, None
        if url.startswith("https://github.com/"):
            return 302, {"Location": "https://codeload.github.com/o/r/zip/HEAD"}, None
        return 200, {"Content-Length": str(len(zip_bytes))}, io.BytesIO(zip_bytes)
    return open_url


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def complete(self, system, user):
        self.calls.append(user)
        return '{"issues": []}'


def write_list(tmp_path, lines):
    path = tmp_path / "repos.csv"
    path.write_text(HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def read_log(tmp_path):
    with open(tmp_path / LOG_NAME, encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


GOOD = "https://github.com/a/good,MIT,Ashish,2026-11-16,yes,fine"
OTHER = "https://github.com/b/other,Apache-2.0,Ashish,2026-11-16,no,"


# ---------- the list ----------

def test_repo_list_rules(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text(
        "\ufeffURL,Licence,Checked_By,checked_on,AI_OK,Note\n"
        "https://github.com/a/good,MIT,Ashish,2026-11-16,yes,fine\n"
        "https://github.com/a/good,MIT,Ashish,2026-11-16,yes,again\n"
        "https://gitlab.com/a/b,MIT,Ashish,2026-11-16,,\n"
        "https://github.com/a/nolicence,unknown,Ashish,2026-11-16,,\n"
        "https://github.com/a/nowho,Apache-2.0,,,,\n"
        "https://github.com/b/other,Apache-2.0,Ashish,2026-11-16,no,\n",
        encoding="utf-8",
    )

    rows, problems = read_repo_list(str(path))

    assert rows == [
        {"owner": "a", "repo": "good", "url": "https://github.com/a/good", "licence": "MIT",
         "checked_by": "Ashish", "checked_on": "2026-11-16", "ai_ok": True, "note": "fine"},
        {"owner": "b", "repo": "other", "url": "https://github.com/b/other", "licence": "Apache-2.0",
         "checked_by": "Ashish", "checked_on": "2026-11-16", "ai_ok": False, "note": ""},
    ]
    assert problems == [
        "row 3: a/good is listed twice.",
        "row 4: Only https://github.com/owner/repository addresses are supported.",
        "row 5: no licence recorded for a/nolicence. Look it up, then fill it in.",
        "row 6: say who checked the licence and when.",
    ]


def test_repo_list_needs_its_columns_and_a_file(tmp_path):
    path = tmp_path / "short.csv"
    path.write_text("url,licence\nhttps://github.com/a/b,MIT\n", encoding="utf-8")

    rows, problems = read_repo_list(str(path))
    assert rows == []
    assert problems == ["The file has no column named: checked_by, checked_on."]

    rows, problems = read_repo_list(str(tmp_path / "missing.csv"))
    assert rows == []
    assert problems == ["The repository list could not be read."]


# ---------- collecting ----------

def test_collect_from_a_repo_list(tmp_path, capsys):
    db = str(tmp_path / "research.db")
    lines = [GOOD, "https://github.com/a/nolicence,unknown,Ashish,2026-11-16,,", OTHER]
    listing = write_list(tmp_path, lines)

    code = collect.main(["--repos", listing, "--db", db], open_url=fake_github())

    assert code == 0
    out = capsys.readouterr().out
    assert "row 3: no licence recorded for a/nolicence" in out
    assert "a/good: 2 files, 1 analysed, 1 issues, saved as run" in out
    assert "b/other: 2 files, 1 analysed, 1 issues, saved as run" in out
    assert "Saved 2 of 2 project(s)" in out

    runs = ResearchStore(db).read_table("runs")
    assert sorted(runs["project_name"]) == ["a/good", "b/other"]

    log = read_log(tmp_path)
    assert len(log) == 2
    first = log[0]
    assert first["source"] == "github"
    assert first["project_name"] == "a/good"
    assert first["url"] == "https://github.com/a/good"
    assert first["licence"] == "MIT"
    assert (first["checked_by"], first["checked_on"]) == ("Ashish", "2026-11-16")
    assert first["archive_root"] == "r-HEAD"
    assert (first["files"], first["analysed"], first["issues"]) == ("2", "1", "1")
    assert first["ai_used"] == "no"
    assert first["note"] == "fine"
    assert first["run_id"] in set(runs["run_id"])


def test_ai_only_for_rows_that_allow_it(tmp_path, monkeypatch, capsys):
    provider = FakeProvider()
    monkeypatch.setattr(collect, "_ai_provider", lambda args, count: (provider, True))
    listing = write_list(tmp_path, [GOOD, OTHER])
    db = str(tmp_path / "research.db")

    code = collect.main(["--repos", listing, "--db", db, "--ai", "--yes"], open_url=fake_github())

    assert code == 0
    assert len(provider.calls) == 2  # both files of a/good. Nothing of b/other
    log = {row["project_name"]: row for row in read_log(tmp_path)}
    assert log["a/good"]["ai_used"] == "yes"
    assert log["b/other"]["ai_used"] == "no"


def test_ai_is_not_asked_for_when_no_row_allows_it(tmp_path, monkeypatch, capsys):
    def must_not_run(args, count):
        raise AssertionError("the AI provider must not be asked for")

    monkeypatch.setattr(collect, "_ai_provider", must_not_run)
    listing = write_list(tmp_path, [OTHER])

    code = collect.main(
        ["--repos", listing, "--db", str(tmp_path / "research.db"), "--ai", "--yes"],
        open_url=fake_github(),
    )

    assert code == 0
    assert "No row has ai_ok=yes" in capsys.readouterr().out


def test_a_failed_fetch_does_not_stop_the_others(tmp_path, capsys):
    listing = write_list(tmp_path, [GOOD, OTHER])
    db = str(tmp_path / "research.db")

    code = collect.main(["--repos", listing, "--db", db], open_url=fake_github(missing=("a/good",)))

    assert code == 0
    out = capsys.readouterr().out
    assert "a/good: not fetched (Repository not found" in out
    assert "Saved 1 of 2 project(s)" in out
    assert list(ResearchStore(db).read_table("runs")["project_name"]) == ["b/other"]


def test_nothing_usable_collects_nothing(tmp_path, capsys):
    listing = write_list(tmp_path, ["https://github.com/a/b,unknown,,,,"])
    db = str(tmp_path / "research.db")

    code = collect.main(["--repos", listing, "--db", db], open_url=fake_github())

    assert code == 1
    assert "No usable rows" in capsys.readouterr().out
    assert not os.path.exists(db)
    assert not (tmp_path / LOG_NAME).exists()


def test_folder_collection_is_logged(tmp_path, capsys):
    folder = tmp_path / "my-project"
    folder.mkdir()
    (folder / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    db = str(tmp_path / "research.db")

    assert collect.main([str(folder), "--db", db]) == 0

    log = read_log(tmp_path)
    assert len(log) == 1
    assert (log[0]["source"], log[0]["project_name"], log[0]["url"], log[0]["licence"]) == (
        "folder", "my-project", "", "")
    assert log[0]["issues"] == "1"


def test_folder_or_repo_list_but_not_both(tmp_path, capsys):
    assert collect.main([]) == 1
    assert "either a folder or --repos" in capsys.readouterr().out

    assert collect.main([str(tmp_path), "--repos", "x.csv"]) == 1
    assert "either a folder or --repos" in capsys.readouterr().out


def test_the_log_header_is_written_once(tmp_path, capsys):
    listing = write_list(tmp_path, [GOOD, OTHER])
    db = str(tmp_path / "research.db")

    collect.main(["--repos", listing, "--db", db], open_url=fake_github())
    collect.main(["--repos", listing, "--db", db], open_url=fake_github())

    raw = (tmp_path / LOG_NAME).read_bytes()
    assert raw.count(b"\xef\xbb\xbf") == 1  # the Excel mark, once, at the start
    assert raw.decode("utf-8-sig").count("collected_at") == 1
    assert len(read_log(tmp_path)) == 4
    assert len(set(row["run_id"] for row in read_log(tmp_path))) == 4  # every run has its own id


def test_the_archive_root_is_remembered():
    project = project_from_zip(make_zip({"r-HEAD/a.py": "x = 1\n"}), "r")

    assert project.source_ref == "r-HEAD"
    assert CodeProject(project_id="p", project_name="p", input_type="project").source_ref == ""