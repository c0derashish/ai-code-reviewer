from analyzer.languages import SOURCE_EXTENSIONS, detect_language, detect_project_languages
from input_manager import from_uploads
from input_manager.models import CodeFile, CodeProject


# ---------- one file ----------

def test_extension_detection():
    cases = {
        "app.py": "python",
        "A.JAVA": "java",
        "x.tsx": "typescript",
        "main.cc": "cpp",
        "util.cs": "csharp",
        "lib.rs": "rust",
        "m.kt": "kotlin",
        "a.mjs": "javascript",
        "index.php": "php",
        "main.go": "go",
        "src/dir/app.py": "python",
    }
    for path, expected in cases.items():
        result = detect_language(path)
        assert result["language"] == expected
        assert result["method"] == "extension"
        assert result["ambiguous"] is False


def test_unknown_extension():
    result = detect_language("notes.txt", "hello")
    assert result["language"] is None
    assert result["method"] == "unknown"


def test_shebang_when_there_is_no_extension():
    assert detect_language("run", "#!/usr/bin/env python3\nprint(1)\n")["language"] == "python"
    assert detect_language("run", "#!/usr/bin/python\n")["language"] == "python"
    assert detect_language("run", "#!/usr/bin/env node\n")["language"] == "javascript"
    assert detect_language("run", "#!/usr/bin/env -S python3 -u\n")["language"] == "python"

    result = detect_language("run", "#!/bin/bash\necho hi\n")
    assert result["language"] is None
    assert result["method"] == "unknown"

    assert detect_language("run", "#!/usr/bin/env python3\n")["method"] == "shebang"


def test_extension_wins_over_shebang():
    result = detect_language("a.py", "#!/usr/bin/env node\n")
    assert result["language"] == "python"
    assert result["method"] == "extension"


def test_h_file_without_cpp_hints_is_c():
    code = "#ifndef A_H\nint add(int a, int b);\n#endif\n"
    result = detect_language("a.h", code)
    assert result["language"] == "c"
    assert result["ambiguous"] is True
    assert result["method"] == "content"


def test_h_file_with_class_is_cpp():
    code = "#pragma once\nclass Point {\n public:\n  int x;\n};\n"
    result = detect_language("a.h", code)
    assert result["language"] == "cpp"
    assert result["ambiguous"] is True


def test_h_file_without_source_defaults_to_c():
    assert detect_language("a.h")["language"] == "c"


def test_supported_extensions_count():
    # Guards against an accidental edit. Same 19 as Phase 1.
    assert len(SOURCE_EXTENSIONS) == 19
    assert ".h" in SOURCE_EXTENSIONS


# ---------- whole project ----------

def test_project_language_mix():
    project = from_uploads(
        "demo",
        [
            ("a.py", b"x = 1\n\ny = 2\n"),
            ("b.py", b"z = 3\n"),
            ("c.js", b"var a = 1;\n"),
        ],
    )
    summary = detect_project_languages(project)

    assert summary["primary_language"] == "python"
    assert summary["primary_language_name"] == "Python"
    assert summary["unknown_files"] == 0
    assert list(summary["languages"]) == ["python", "javascript"]
    assert summary["languages"]["python"] == {
        "name": "Python", "files": 2, "lines": 3, "percentage": 75.0,
    }
    assert summary["languages"]["javascript"] == {
        "name": "JavaScript", "files": 1, "lines": 1, "percentage": 25.0,
    }

    # the project and its files were filled in too
    assert project.primary_language == "python"
    assert project.get_file("a.py").language == "python"
    assert project.get_file("c.js").language == "javascript"


def test_tie_on_lines_and_files_uses_alphabetical_order():
    project = from_uploads("demo", [("a.py", b"x = 1\n"), ("b.js", b"var a;\n")])
    summary = detect_project_languages(project)
    assert summary["primary_language"] == "javascript"


def test_tie_on_lines_uses_more_files():
    project = from_uploads(
        "demo",
        [("a.py", b"x = 1\ny = 2\n"), ("b.js", b"var a;\n"), ("c.js", b"var b;\n")],
    )
    summary = detect_project_languages(project)
    assert summary["languages"]["python"]["lines"] == 2
    assert summary["languages"]["javascript"]["lines"] == 2
    assert summary["primary_language"] == "javascript"  # 2 files beat 1 file


def test_all_blank_lines_uses_file_share():
    project = from_uploads("demo", [("a.py", b"\n\n"), ("b.js", b"   \n")])
    summary = detect_project_languages(project)
    assert summary["languages"]["python"]["percentage"] == 50.0
    assert summary["languages"]["javascript"]["percentage"] == 50.0
    assert summary["primary_language"] == "javascript"


def test_percentages_are_rounded_to_one_decimal():
    project = from_uploads(
        "demo",
        [("a.py", b"x = 1\n"), ("b.js", b"var a;\n"), ("c.go", b"package main\n")],
    )
    summary = detect_project_languages(project)
    for entry in summary["languages"].values():
        assert entry["percentage"] == 33.3
    assert summary["primary_language"] == "go"


def test_empty_project_has_no_languages():
    project = CodeProject(project_id="p", project_name="p", input_type="project")
    summary = detect_project_languages(project)
    assert summary["primary_language"] is None
    assert summary["languages"] == {}
    assert summary["unknown_files"] == 0


def test_unknown_file_is_counted_not_hidden():
    project = CodeProject(project_id="p", project_name="p", input_type="project")
    project.files.append(CodeFile("notes.txt", "hi", 2))
    summary = detect_project_languages(project)
    assert summary["unknown_files"] == 1
    assert summary["primary_language"] is None
    assert project.files[0].language is None