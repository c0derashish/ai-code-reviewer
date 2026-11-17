import pytest

from analyzer.findings import duplication_to_issues
from analyzer.languages import detect_project_languages
from analyzer.static import duplication
from analyzer.static.duplication import find_duplicates, window_hashes
from analyzer.static.runner import analyze_project
from analyzer.validation import validate_project
from input_manager import from_uploads

A_CODE = "def add(a, b):\n    total = a + b\n    return total\n"
# the same code as A_CODE, with other comments, blank lines and spacing
B_CODE = "# copy\ndef add(a,   b):\n\n    total = a + b   # sum\n    return total\n"

SMALL = {"min_tokens": 10, "min_lines": 3}


def make_project(files):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    validate_project(project)
    analyze_project(project)
    return project


def test_window_hashes_match_for_equal_windows():
    hashes = window_hashes([1, 2, 3, 1, 2, 3], 3)
    assert len(hashes) == 4
    assert hashes[0] == hashes[3]
    assert hashes[0] != hashes[1]
    assert window_hashes([1, 2], 3) == []


def test_identical_code_in_two_files_is_found():
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project, **SMALL)

    assert report["status"] == "ok"
    assert report["settings"] == {"min_tokens": 10, "min_lines": 3}
    assert report["files_checked"] == 2
    assert report["clone_count"] == 1
    assert report["clones"] == [
        {
            "id": 1,
            "tokens": 20,
            "first": {"file_path": "a.py", "start_line": 1, "end_line": 3, "lines": 3},
            "second": {"file_path": "b.py", "start_line": 2, "end_line": 5, "lines": 4},
        }
    ]


def test_different_code_has_no_clones():
    other = "def sub(a, b):\n    diff = a - b\n    return diff\n"
    project = make_project({"a.py": A_CODE, "b.py": other})
    report = find_duplicates(project, **SMALL)

    assert report["clone_count"] == 0
    assert report["duplication_ratio"] == 0.0


def test_short_code_is_below_the_default_limits():
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project)  # 50 tokens, 5 lines. Our code has only 20 tokens

    assert report["clone_count"] == 0


def test_renamed_variables_are_not_found():
    renamed = "def add(a, b):\n    result = a + b\n    return result\n"
    project = make_project({"a.py": A_CODE, "b.py": renamed})
    report = find_duplicates(project, **SMALL)

    assert report["clone_count"] == 0  # a known limit. See methodology.md


def test_repeated_block_in_one_file():
    code = "x = foo(1)\ny = bar(2)\n" * 3
    project = make_project({"a.py": code})
    report = find_duplicates(project, min_tokens=10, min_lines=2)

    first = {"file_path": "a.py", "start_line": 1, "end_line": 2, "lines": 2}
    assert report["clones"] == [
        {"id": 1, "tokens": 14, "first": first,
         "second": {"file_path": "a.py", "start_line": 3, "end_line": 4, "lines": 2}},
        {"id": 2, "tokens": 14, "first": first,
         "second": {"file_path": "a.py", "start_line": 5, "end_line": 6, "lines": 2}},
    ]
    assert report["duplication_ratio"] == 100.0


def test_duplication_ratio_per_file_and_project():
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project, **SMALL)

    assert report["duplicated_lines"] == 6
    assert report["total_lines"] == 7
    assert report["duplication_ratio"] == 85.7
    assert report["files"]["a.py"] == {"duplicated_lines": 3, "total_lines": 3, "ratio": 100.0}
    assert report["files"]["b.py"] == {"duplicated_lines": 3, "total_lines": 4, "ratio": 75.0}
    assert project.get_file("b.py").analysis_result["duplication"] == report["files"]["b.py"]


def test_duplicate_becomes_vedix_issue():
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project, **SMALL)
    issues = duplication_to_issues(project, report)

    assert len(issues) == 1
    issue = issues[0]
    assert issue["id"] == "duplicate-1"
    assert issue["file_path"] == "b.py"
    assert issue["line"] == 2
    assert issue["severity"] == "low"
    assert issue["category"] == "code_smell"
    assert issue["title"] == "Duplicate code (4 lines)"
    assert issue["before"] == "def add(a,   b):"
    assert issue["explanation"].startswith("Lines 2-5 repeat lines 1-3 of a.py")
    assert issue["source"] == "duplication"
    assert issue["rule"] == "duplicate_code"


def test_only_valid_python_files_are_checked():
    project = make_project({
        "a.py": A_CODE,
        "b.py": B_CODE,
        "bad.py": "def broken(:\n",
        "c.js": "var a = 1;\n",
    })
    report = find_duplicates(project, **SMALL)

    assert report["files_checked"] == 2
    assert report["clone_count"] == 1


def test_bad_settings_are_refused():
    project = make_project({"a.py": A_CODE})
    with pytest.raises(ValueError):
        find_duplicates(project, min_tokens=5)
    with pytest.raises(ValueError):
        find_duplicates(project, min_lines=0)


def test_too_large_project_is_skipped(monkeypatch):
    monkeypatch.setattr(duplication, "MAX_TOTAL_TOKENS", 10)
    project = make_project({"a.py": A_CODE, "b.py": B_CODE})
    report = find_duplicates(project, **SMALL)

    assert report["status"] == "skipped"
    assert "too large" in report["note"]


def test_no_python_files_is_skipped():
    project = make_project({"c.js": "var a = 1;\n"})
    report = find_duplicates(project, **SMALL)

    assert report["status"] == "skipped"
    assert report["note"] == "No Python files to check."