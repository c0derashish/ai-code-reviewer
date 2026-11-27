import io
import stat
import zipfile

import pytest

from repo_fetcher import archive
from repo_fetcher.archive import project_from_zip
from repo_fetcher.github import (
    MAX_REDIRECTS,
    FetchError,
    archive_url,
    fetch_archive,
    parse_github_url,
)
from repo_fetcher.service import fetch_repository


def make_zip(files, symlinks=()):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for name, content in files.items():
            target.writestr(name, content)
        for name, link in symlinks:
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            target.writestr(info, link)
    return buffer.getvalue()


class FakeNetwork:
    """Answers each request with the next prepared (status, headers, stream)."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.answers.pop(0)


class NoRead:
    def read(self, size):
        raise AssertionError("the body must not be read")


class Broken:
    def read(self, size):
        raise OSError("connection lost")


def error_text(action):
    with pytest.raises(FetchError) as info:
        action()
    return str(info.value)


# ---------- the address ----------

def test_parse_valid_addresses():
    same = ("octocat", "Hello-World")
    assert parse_github_url("https://github.com/octocat/Hello-World") == same
    assert parse_github_url("  https://github.com/octocat/Hello-World/  ") == same
    assert parse_github_url("https://github.com/octocat/Hello-World.git") == same
    assert parse_github_url("https://GitHub.com/octocat/hello.world_x") == ("octocat", "hello.world_x")
    assert parse_github_url("https://github.com:443/a/b") == ("a", "b")


def test_parse_refuses_bad_addresses():
    cases = [
        ("", "Enter"), ("   ", "Enter"), (None, "Enter"),
        ("http://github.com/a/b", "Only https"),
        ("https://gitlab.com/a/b", "Only https"),
        ("https://www.github.com/a/b", "Only https"),
        ("not a url", "Only https"),
        ("https://user:pass@github.com/a/b", "credentials"),
        ("https://github.com/a/b?tab=x", "credentials"),
        ("https://github.com/a/b#readme", "credentials"),
        ("https://github.com:8080/a/b", "not valid"),
        ("https://github.com/", "must look like"),
        ("https://github.com/a", "must look like"),
        ("https://github.com/a/b/tree/main", "must look like"),
        ("https://github.com/a/..", "characters"),
        ("https://github.com/a/.", "characters"),
        ("https://github.com/a/.git", "characters"),
        ("https://github.com/a/b%2e", "characters"),
        ("https://github.com/-bad/b", "characters"),
        ("https://github.com/" + "a" * 40 + "/b", "characters"),
    ]
    for text, fragment in cases:
        message = error_text(lambda: parse_github_url(text))
        assert fragment in message, text
        assert "pass" not in message


def test_archive_url():
    assert archive_url("octocat", "Hello-World") == "https://github.com/octocat/Hello-World/archive/HEAD.zip"


# ---------- downloading ----------

def test_fetch_follows_github_redirects():
    data = make_zip({"r-HEAD/a.py": "x = 1\n"})
    network = FakeNetwork(
        (302, {"location": "https://codeload.github.com/octocat/Hello-World/zip/HEAD"}, None),
        (200, {"Content-Length": str(len(data))}, io.BytesIO(data)),
    )

    assert fetch_archive("octocat", "Hello-World", network) == data
    assert network.urls == [
        "https://github.com/octocat/Hello-World/archive/HEAD.zip",
        "https://codeload.github.com/octocat/Hello-World/zip/HEAD",
    ]


def test_fetch_refuses_other_redirect_targets():
    bad_targets = [
        "https://evil.example/x.zip",
        "//evil.example/x.zip",
        "http://codeload.github.com/x",
        "https://user:pw@codeload.github.com/x",
        "https://codeload.github.com:8080/x",
        "ftp://github.com/x",
    ]
    for target in bad_targets:
        network = FakeNetwork((302, {"Location": target}, None))
        assert "redirect" in error_text(lambda: fetch_archive("o", "r", network)), target
        assert len(network.urls) == 1  # the bad address was never requested


def test_fetch_refuses_a_redirect_without_address():
    network = FakeNetwork((302, {}, None))
    assert "without an address" in error_text(lambda: fetch_archive("o", "r", network))


def test_fetch_stops_after_too_many_redirects():
    redirect = (302, {"Location": "https://github.com/o/r/archive/HEAD.zip"}, None)
    network = FakeNetwork(*[redirect] * 10)

    assert "too many times" in error_text(lambda: fetch_archive("o", "r", network))
    assert len(network.urls) == MAX_REDIRECTS + 1


def test_fetch_explains_http_errors():
    cases = [(404, "not found"), (403, "limiting"), (429, "limiting"), (451, "legal"),
             (500, "problem"), (503, "problem"), (418, "418")]
    for status, fragment in cases:
        network = FakeNetwork((status, {}, None))
        assert fragment in error_text(lambda: fetch_archive("o", "r", network))


def test_download_size_limit_from_the_header():
    network = FakeNetwork((200, {"Content-Length": "5000"}, NoRead()))
    assert "larger than" in error_text(lambda: fetch_archive("o", "r", network, max_bytes=1000))


def test_download_size_limit_without_a_header():
    network = FakeNetwork((200, {}, io.BytesIO(b"x" * 5000)))
    assert "larger than" in error_text(lambda: fetch_archive("o", "r", network, max_bytes=1000))

    exactly = FakeNetwork((200, {}, io.BytesIO(b"x" * 1000)))
    assert len(fetch_archive("o", "r", exactly, max_bytes=1000)) == 1000


def test_download_deadline_and_broken_stream():
    slow = FakeNetwork((200, {}, io.BytesIO(b"x")))
    assert "too long" in error_text(lambda: fetch_archive("o", "r", slow, deadline_seconds=0))

    broken = FakeNetwork((200, {}, Broken()))
    assert "interrupted" in error_text(lambda: fetch_archive("o", "r", broken))


def test_streams_are_closed():
    done = io.BytesIO(b"abc")
    fetch_archive("o", "r", FakeNetwork((200, {}, done)))
    assert done.closed

    too_big = io.BytesIO(b"x" * 5000)
    error_text(lambda: fetch_archive("o", "r", FakeNetwork((200, {}, too_big)), max_bytes=1000))
    assert too_big.closed


def test_network_errors_pass_through():
    def unreachable(url):
        raise FetchError("Cannot reach GitHub.")

    assert error_text(lambda: fetch_archive("o", "r", unreachable)) == "Cannot reach GitHub."


# ---------- unpacking ----------

def test_project_from_a_github_archive():
    data = make_zip(
        {
            "Hello-World-HEAD/": "",
            "Hello-World-HEAD/src/": "",
            "Hello-World-HEAD/src/app.py": "x = 1\n",
            "Hello-World-HEAD/src/util.js": "var a = 1;\n",
            "Hello-World-HEAD/README.md": "# hi\n",
            "Hello-World-HEAD/image.png": b"\x89PNG\x00",
            "Hello-World-HEAD/node_modules/lib.js": "z = 3\n",
            "Hello-World-HEAD/empty.py": "",
        },
        symlinks=[("Hello-World-HEAD/src/link.py", "app.py")],
    )

    project = project_from_zip(data, "Hello-World")

    assert project.project_name == "Hello-World"
    assert project.input_type == "project"
    assert [f.file_path for f in project.files] == ["src/app.py", "src/util.js"]
    assert project.files[0].source_code == "x = 1\n"
    assert project.skipped_count == 5
    assert {item.file_path: item.reason for item in project.skipped} == {
        "README.md": "unsupported file type",
        "image.png": "unsupported file type",
        "node_modules/lib.js": "inside an ignored folder",
        "empty.py": "empty file",
        "src/link.py": "symbolic link",
    }


def test_unsafe_names_in_an_archive_are_skipped():
    data = make_zip({
        "r/ok.py": "x = 1\n",
        "r/../evil.py": "y = 2\n",
        "/abs.py": "z = 3\n",
        "top.py": "w = 4\n",
    })

    project = project_from_zip(data, "r")

    assert [f.file_path for f in project.files] == ["ok.py"]
    assert {item.file_path: item.reason for item in project.skipped} == {
        "../evil.py": "path goes outside the project",
        "/abs.py": "unusable path",
        "top.py": "unusable path",
    }


def test_too_many_entries(monkeypatch):
    data = make_zip({f"r/f{n}.py": "x = 1\n" for n in range(5)})
    monkeypatch.setattr(archive, "MAX_SCANNED_ENTRIES", 3)

    assert "too many files" in error_text(lambda: project_from_zip(data, "r"))


def test_too_much_source_data(monkeypatch):
    data = make_zip({"r/a.py": "x = 1\n\n", "r/b.py": "y = 2\n\n"})  # 8 bytes each
    monkeypatch.setattr(archive, "MAX_CANDIDATE_BYTES", 10)

    assert "too large" in error_text(lambda: project_from_zip(data, "r"))


def test_unreadable_archive():
    assert "could not be read" in error_text(lambda: project_from_zip(b"not a zip", "r"))


def test_archive_without_source_files():
    data = make_zip({"r/README.md": "# hi\n", "r/LICENSE": "MIT\n"})

    assert "No supported source files found" in error_text(lambda: project_from_zip(data, "r"))


def test_too_many_source_files():
    data = make_zip({f"r/f{n}.py": "x = 1\n" for n in range(501)})

    assert "Too many files" in error_text(lambda: project_from_zip(data, "r"))


def test_fetch_repository_end_to_end():
    data = make_zip({"Hello-World-HEAD/app.py": "x = 1\n"})
    network = FakeNetwork(
        (302, {"Location": "https://codeload.github.com/octocat/Hello-World/zip/HEAD"}, None),
        (200, {"Content-Length": str(len(data))}, io.BytesIO(data)),
    )

    project = fetch_repository("octocat", "Hello-World", network)

    assert project.project_name == "Hello-World"
    assert [f.file_path for f in project.files] == ["app.py"]