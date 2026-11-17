from analyzer.findings import CATEGORIES, SEVERITIES, validation_to_issues
from analyzer.languages import detect_project_languages
from analyzer.validation import validate_project
from input_manager import from_uploads
from input_manager.models import CodeFile, CodeProject


def make_project(files):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    return project


def result_of(project, path):
    return project.get_file(path).validation_result


# ---------- the stages ----------

def test_valid_python_file():
    project = make_project({"a.py": "x = 1\n"})
    summary = validate_project(project)

    assert summary == {
        "files": 1, "valid": 1, "invalid": 0, "not_checked": 0, "errors": 0, "warnings": 0,
    }
    result = result_of(project, "a.py")
    assert result["status"] == "valid"
    assert result["valid"] is True


def test_syntax_error_makes_file_invalid():
    project = make_project({"a.py": "def broken(:\n    pass\n"})
    summary = validate_project(project)

    assert summary == {
        "files": 1, "valid": 0, "invalid": 1, "not_checked": 0, "errors": 1, "warnings": 0,
    }
    result = result_of(project, "a.py")
    assert result["status"] == "invalid"
    assert result["errors"][0]["stage"] == "syntax"
    assert result["errors"][0]["severity"] == "error"
    assert result["errors"][0]["line"] == 1
    assert result["dependencies"] is None  # not checked, the code cannot be read


def test_compile_stage_error():
    project = make_project({"a.py": "return 1\n"})
    validate_project(project)

    result = result_of(project, "a.py")
    assert result["status"] == "invalid"
    assert result["errors"][0]["stage"] == "compile"


def test_other_languages_are_not_checked():
    project = make_project({"a.js": "var a = 1;\n"})
    summary = validate_project(project)

    assert summary == {
        "files": 1, "valid": 0, "invalid": 0, "not_checked": 1, "errors": 0, "warnings": 0,
    }
    result = result_of(project, "a.js")
    assert result["status"] == "not_checked"
    assert result["valid"] is None
    assert "No JavaScript validator" in result["note"]


def test_unrecognized_language_is_not_checked():
    project = CodeProject(project_id="p", project_name="p", input_type="project")
    project.files.append(CodeFile("notes.txt", "hi", 2))  # language stays None
    validate_project(project)

    result = result_of(project, "notes.txt")
    assert result["status"] == "not_checked"
    assert "not recognized" in result["note"]


# ---------- dependencies ----------

def test_dependencies_are_sorted_into_groups():
    project = make_project({
        "main.py": (
            "import os\n"
            "import requests\n"
            "import utils\n"
            "from pkg.mod import f\n"
            "from .missing import x\n"
        ),
        "utils.py": "x = 1\n",
        "pkg/mod.py": "def f():\n    pass\n",
    })
    summary = validate_project(project)

    main = result_of(project, "main.py")
    assert main["status"] == "valid"  # a warning does not make a file invalid
    assert main["dependencies"] == {
        "standard_library": ["os"],
        "local": ["pkg", "utils"],
        "external": ["requests"],
    }

    assert len(main["errors"]) == 1
    error = main["errors"][0]
    assert error["type"] == "MissingLocalModule"
    assert error["stage"] == "dependency"
    assert error["severity"] == "warning"
    assert error["line"] == 5
    assert error["column"] == 1
    assert "missing" in error["message"]

    assert result_of(project, "utils.py")["dependencies"] == {
        "standard_library": [], "local": [], "external": [],
    }
    assert summary == {
        "files": 3, "valid": 3, "invalid": 0, "not_checked": 0, "errors": 0, "warnings": 1,
    }


def test_missing_submodule_of_a_local_package():
    project = make_project({"pkg/mod.py": "x = 1\n", "main.py": "import pkg.nope\n"})
    validate_project(project)

    errors = result_of(project, "main.py")["errors"]
    assert errors[0]["type"] == "MissingLocalModule"
    assert errors[0]["line"] == 1


def test_local_file_shadows_standard_library():
    project = make_project({"random.py": "x = 1\n", "main.py": "import random\n"})
    validate_project(project)

    assert result_of(project, "main.py")["dependencies"] == {
        "standard_library": [], "local": ["random"], "external": [],
    }


def test_relative_imports_that_exist_are_fine():
    project = make_project({
        "pkg/mod.py": "from .other import z\nfrom ..top import t\n",
        "pkg/other.py": "z = 1\n",
        "top.py": "t = 1\n",
    })
    validate_project(project)

    result = result_of(project, "pkg/mod.py")
    assert result["errors"] == []
    assert result["status"] == "valid"


def test_relative_import_above_the_project():
    project = make_project({"pkg/mod.py": "from ...x import y\n"})
    validate_project(project)

    result = result_of(project, "pkg/mod.py")
    assert result["errors"][0]["type"] == "RelativeImportError"
    assert result["status"] == "valid"


# ---------- issues for VEDIX ----------

def test_validation_errors_become_vedix_issues():
    project = make_project({
        "bad.py": "x = 1\ndef broken(:\n    pass\n",
        "main.py": "from .nope import x\n",
    })
    validate_project(project)
    issues = validation_to_issues(project)

    assert len(issues) == 2

    first = issues[0]
    assert first["file_path"] == "bad.py"
    assert first["line"] == 2
    assert first["severity"] == "high"
    assert first["category"] == "bug"
    assert first["title"] == "Syntax error"
    assert first["explanation"].startswith("Python cannot read this code.")
    assert first["suggestion"]
    assert first["before"] == "def broken(:"

    second = issues[1]
    assert second["file_path"] == "main.py"
    assert second["line"] == 1
    assert second["severity"] == "medium"
    assert second["title"] == "Import cannot be resolved"
    assert second["before"] == "from .nope import x"

    assert len({issue["id"] for issue in issues}) == 2
    for issue in issues:
        assert issue["severity"] in SEVERITIES
        assert issue["category"] in CATEGORIES


def test_issue_line_is_always_inside_the_file():
    # null bytes: Python may give no line number at all
    project = CodeProject(project_id="p", project_name="p", input_type="single_file")
    project.files.append(CodeFile("a.py", "x = 1\0\n", 7, language="python"))
    validate_project(project)

    issues = validation_to_issues(project)
    assert len(issues) == 1
    assert issues[0]["line"] == 1


def test_no_issues_when_nothing_is_wrong():
    project = make_project({"a.py": "x = 1\n"})
    assert validation_to_issues(project) == []  # not validated yet

    validate_project(project)
    assert validation_to_issues(project) == []  # validated, nothing wrong