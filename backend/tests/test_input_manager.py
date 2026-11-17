import os

import pytest

from input_manager.models import InputError
from input_manager.rules import MAX_FILE_BYTES, MAX_SKIPPED_LISTED, clean_path
from input_manager.sources import (
    from_local_file,
    from_local_folder,
    from_single_file,
    from_uploads,
)


def paths_of(project):
    return [code_file.file_path for code_file in project.files]


# ---------- path cleaning ----------

def test_clean_path_accepts_normal_paths():
    assert clean_path("src\\app.py") == ("src/app.py", None)
    assert clean_path("./a//b.py") == ("a/b.py", None)
    assert clean_path("app.py") == ("app.py", None)


def test_clean_path_rejects_unsafe_paths():
    bad_paths = [
        "", "   ", "../x.py", "a/../../b.py", "/etc/passwd",
        "C:\\x.py", "\\\\server\\share\\x.py", "a\x00b.py",
    ]
    for bad in bad_paths:
        path, reason = clean_path(bad)
        assert path is None
        assert reason


# ---------- single file ----------

def test_single_file_ok():
    project = from_single_file("app.py", b"x = 1\n")
    assert project.input_type == "single_file"
    assert project.project_name == "app.py"
    assert paths_of(project) == ["app.py"]
    assert project.files[0].source_code == "x = 1\n"
    assert project.files[0].size_bytes == 6


def test_single_file_drops_folder_part():
    project = from_single_file("some/dir/app.py", b"x = 1\n")
    assert paths_of(project) == ["app.py"]


def test_single_file_unsupported_type():
    with pytest.raises(InputError) as info:
        from_single_file("notes.txt", b"hello")
    assert "unsupported" in str(info.value)


def test_single_file_binary():
    with pytest.raises(InputError) as info:
        from_single_file("a.py", b"\x00\x01\x02")
    assert "binary" in str(info.value)


def test_single_file_empty():
    with pytest.raises(InputError) as info:
        from_single_file("a.py", b"")
    assert "empty" in str(info.value)


def test_single_file_too_large():
    with pytest.raises(InputError) as info:
        from_single_file("a.py", b"x" * (MAX_FILE_BYTES + 1))
    assert "larger" in str(info.value)


def test_byte_order_mark_is_removed():
    project = from_single_file("a.py", b"\xef\xbb\xbfx = 1\n")
    assert project.files[0].source_code == "x = 1\n"


def test_invalid_utf8_is_refused():
    with pytest.raises(InputError) as info:
        from_single_file("a.py", b"x = '\xe9'\n")  # a Latin-1 letter, not UTF-8
    assert "UTF-8" in str(info.value)


# ---------- uploads (what the API will use) ----------

def test_uploads_project_skips_junk():
    items = [
        ("src/app.py", b"x = 1\n"),
        ("src/node_modules/x.js", b"y = 1\n"),
        ("README.md", b"# hi\n"),
        ("../evil.py", b"z = 1\n"),
    ]
    project = from_uploads("demo", items)
    assert project.input_type == "project"
    assert paths_of(project) == ["src/app.py"]
    assert project.skipped_count == 3


def test_uploads_one_item_is_single_file_and_keeps_path():
    project = from_uploads("demo", [("src/app.py", b"x = 1\n")])
    assert project.input_type == "single_file"
    assert paths_of(project) == ["src/app.py"]


def test_uploads_with_nothing_usable():
    with pytest.raises(InputError) as info:
        from_uploads("demo", [("a.txt", b"hi")])
    assert "No supported" in str(info.value)


def test_uploads_too_many_files():
    items = [(f"f{i}.py", b"x = 1\n") for i in range(501)]
    with pytest.raises(InputError) as info:
        from_uploads("demo", items)
    assert "Too many files" in str(info.value)


def test_uploads_total_size_limit():
    data = b"x" * MAX_FILE_BYTES  # exactly 2 MB, allowed alone
    items = [(f"f{i}.py", data) for i in range(13)]  # 26 MB in total
    with pytest.raises(InputError) as info:
        from_uploads("demo", items)
    assert "25 MB" in str(info.value)


def test_duplicate_path_is_skipped():
    project = from_uploads("demo", [("a.py", b"x = 1\n"), ("a.py", b"y = 2\n")])
    assert paths_of(project) == ["a.py"]
    assert project.files[0].source_code == "x = 1\n"
    assert project.skipped_count == 1


def test_skipped_list_is_capped():
    items = [(f"img{i}.png", b"x") for i in range(300)]
    items.append(("a.py", b"x = 1\n"))
    project = from_uploads("demo", items)
    assert project.skipped_count == 300
    assert len(project.skipped) == MAX_SKIPPED_LISTED


# ---------- local disk ----------

def test_local_folder(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "src" / "app.py").write_bytes(b"x = 1\n")
    (tmp_path / "src" / "util.py").write_bytes(b"y = 2\n")
    (tmp_path / "node_modules" / "lib.js").write_bytes(b"z = 3\n")
    (tmp_path / "README.md").write_bytes(b"# hi\n")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\x00\x01")

    project = from_local_folder(str(tmp_path))
    assert project.input_type == "project"
    assert project.project_name == os.path.basename(os.path.realpath(str(tmp_path)))
    assert paths_of(project) == ["src/app.py", "src/util.py"]
    # README.md and image.png are skipped. node_modules is never entered
    assert project.skipped_count == 2


def test_local_folder_missing(tmp_path):
    with pytest.raises(InputError) as info:
        from_local_folder(str(tmp_path / "nope"))
    assert "not found" in str(info.value)


def test_local_file(tmp_path):
    (tmp_path / "app.py").write_bytes(b"x = 1\n")
    project = from_local_file(str(tmp_path / "app.py"))
    assert project.input_type == "single_file"
    assert paths_of(project) == ["app.py"]


def test_symlinks_are_skipped(tmp_path):
    real = tmp_path / "real.py"
    real.write_bytes(b"x = 1\n")
    try:
        os.symlink(real, tmp_path / "link.py")
    except (OSError, NotImplementedError):
        pytest.skip("this computer does not allow creating symbolic links")

    project = from_local_folder(str(tmp_path))
    assert paths_of(project) == ["real.py"]