import ast

import pytest

from analyzer.findings import CATEGORIES, SEVERITIES, static_to_issues
from analyzer.languages import detect_project_languages
from analyzer.static.python.code_smells import DEFAULT_THRESHOLDS, find_smells
from analyzer.static.python.documentation import measure_documentation
from analyzer.static.python.function_analyzer import collect_structure, summarize_functions
from analyzer.static.runner import METRICS_VERSION, analyze_project
from analyzer.validation import validate_project
from input_manager import from_uploads

CODE = "\n".join([
    '"""Module doc."""',                          # 1
    "",                                           # 2
    "class Calculator:",                          # 3
    '    """A calculator."""',                    # 4
    "",                                           # 5
    "    def add(self, a, b):",                   # 6
    '        """Add two numbers."""',            # 7
    "        return a + b",                       # 8
    "",                                           # 9
    "    def divide(self, a, b=1, *args, **kwargs):",  # 10
    "        if b == 0:",                         # 11
    "            return None",                    # 12
    "        return a / b",                       # 13
    "",                                           # 14
    "",                                           # 15
    "def helper(x):",                             # 16
    "    for i in x:",                            # 17
    "        if i and i > 0:",                    # 18
    "            print(i)",                       # 19
    "",
])

LOW_LIMITS = {
    "long_method_lines": 3,
    "max_parameters": 1,
    "max_nesting_depth": 1,
    "max_complexity": 3,
    "large_class_lines": 10,
    "large_class_methods": 1,
}


def structure_of(code):
    tree = ast.parse(code)
    functions, classes = collect_structure(tree)
    return tree, functions, classes


def make_project(files):
    items = [(path, text.encode("utf-8")) for path, text in files.items()]
    project = from_uploads("demo", items)
    detect_project_languages(project)
    return project


# ---------- functions and classes ----------

def test_function_metrics():
    _, functions, _ = structure_of(CODE)

    assert functions == [
        {
            "name": "add", "qualified_name": "Calculator.add",
            "start_line": 6, "end_line": 8, "length": 3, "parameters": 2,
            "cyclomatic_complexity": 1, "max_nesting_depth": 0, "returns": 1,
            "conditional_expressions": 0, "has_docstring": True, "is_method": True,
        },
        {
            "name": "divide", "qualified_name": "Calculator.divide",
            "start_line": 10, "end_line": 13, "length": 4, "parameters": 4,
            "cyclomatic_complexity": 2, "max_nesting_depth": 1, "returns": 2,
            "conditional_expressions": 0, "has_docstring": False, "is_method": True,
        },
        {
            "name": "helper", "qualified_name": "helper",
            "start_line": 16, "end_line": 19, "length": 4, "parameters": 1,
            "cyclomatic_complexity": 4, "max_nesting_depth": 2, "returns": 0,
            "conditional_expressions": 0, "has_docstring": False, "is_method": False,
        },
    ]


def test_function_summary():
    _, functions, _ = structure_of(CODE)
    assert summarize_functions(functions) == {
        "function_count": 3,
        "average_length": 3.7,
        "max_length": 4,
        "average_complexity": 2.3,
        "max_complexity": 4,
        "max_nesting_depth": 2,
    }
    assert summarize_functions([])["function_count"] == 0
    assert summarize_functions([])["average_length"] is None


def test_class_metrics():
    _, _, classes = structure_of(CODE)
    assert classes == [
        {
            "name": "Calculator", "qualified_name": "Calculator",
            "start_line": 3, "end_line": 13, "length": 11,
            "methods": 2, "has_docstring": True,
        }
    ]


def test_nested_functions_are_measured_separately():
    code = "\n".join([
        "def outer(a):",
        "    def inner(b):",
        "        if b:",
        "            return 1",
        "        return 2",
        "    if a:",
        "        return inner(a)",
        "    return 0",
        "",
    ])
    _, functions, _ = structure_of(code)
    outer, inner = functions

    assert outer["qualified_name"] == "outer"
    assert (outer["start_line"], outer["end_line"], outer["length"]) == (1, 8, 8)
    assert outer["cyclomatic_complexity"] == 2  # only its own "if a"
    assert outer["max_nesting_depth"] == 1
    assert outer["returns"] == 2

    assert inner["qualified_name"] == "outer.inner"
    assert (inner["start_line"], inner["end_line"], inner["length"]) == (2, 5, 4)
    assert inner["cyclomatic_complexity"] == 2
    assert inner["returns"] == 2


def test_parameter_counting_for_static_and_class_methods():
    code = "\n".join([
        "class A:",
        "    @staticmethod",
        "    def f(x, y):",
        "        return x",
        "",
        "    @classmethod",
        "    def g(cls, z):",
        "        return z",
        "",
    ])
    _, functions, classes = structure_of(code)
    assert [f["parameters"] for f in functions] == [2, 1]
    assert all(f["is_method"] for f in functions)
    assert classes[0]["methods"] == 2


def test_async_function_is_collected():
    _, functions, _ = structure_of("async def f():\n    return 1\n")
    assert len(functions) == 1
    assert functions[0]["name"] == "f"
    assert functions[0]["is_method"] is False


# ---------- documentation ----------

def test_documentation_coverage():
    tree, functions, classes = structure_of(CODE)
    assert measure_documentation(tree, functions, classes) == {
        "module_docstring": True,
        "functions": {"documented": 1, "total": 3},
        "classes": {"documented": 1, "total": 1},
        "coverage_percent": 50.0,
    }


def test_documentation_with_no_definitions():
    tree, functions, classes = structure_of("x = 1\n")
    assert measure_documentation(tree, functions, classes) == {
        "module_docstring": False,
        "functions": {"documented": 0, "total": 0},
        "classes": {"documented": 0, "total": 0},
        "coverage_percent": None,
    }


def test_empty_docstring_is_not_documentation():
    _, functions, _ = structure_of('def f():\n    """   """\n    return 1\n')
    assert functions[0]["has_docstring"] is False


# ---------- smells ----------

def test_default_thresholds_find_nothing_in_small_code():
    _, functions, classes = structure_of(CODE)
    assert find_smells(functions, classes) == []

    with pytest.raises(ValueError):
        find_smells([], [], {"typo": 1})


def test_smells_with_low_thresholds():
    _, functions, classes = structure_of(CODE)
    smells = find_smells(functions, classes, LOW_LIMITS)

    assert [(smell["rule"], smell["target"]) for smell in smells] == [
        ("too_many_parameters", "Calculator.add"),
        ("long_method", "Calculator.divide"),
        ("too_many_parameters", "Calculator.divide"),
        ("long_method", "helper"),
        ("deep_nesting", "helper"),
        ("high_complexity", "helper"),
        ("large_class", "Calculator"),
    ]
    assert [smell["line"] for smell in smells] == [6, 10, 10, 16, 16, 16, 3]

    last = smells[-1]
    assert last["value"] == 11
    assert last["threshold"] == 10
    assert last["kind"] == "class"


# ---------- running on a project ----------

def test_runner_marks_files_it_cannot_analyze():
    project = make_project({
        "good.py": "def f(x):\n    return x\n",
        "bad.py": "def broken(:\n",
        "a.js": "var a = 1;\n",
    })
    validate_project(project)
    summary = analyze_project(project)

    assert summary == {"analyzed": 1, "not_analyzed": 2, "smells": 0}

    good = project.get_file("good.py").analysis_result
    assert good["status"] == "analyzed"
    assert good["functions"][0]["length"] == 2

    assert "errors" in project.get_file("bad.py").analysis_result["note"]
    assert "Python" in project.get_file("a.js").analysis_result["note"]


def test_runner_needs_validation_first():
    project = make_project({"good.py": "x = 1\n"})
    summary = analyze_project(project)  # validate_project was not called

    assert summary == {"analyzed": 0, "not_analyzed": 1, "smells": 0}
    assert "not been validated" in project.get_file("good.py").analysis_result["note"]


def test_analysis_result_has_version_and_thresholds():
    project = make_project({"good.py": "x = 1\n"})
    validate_project(project)
    analyze_project(project)

    result = project.get_file("good.py").analysis_result
    assert result["metrics_version"] == METRICS_VERSION
    assert result["thresholds"] == DEFAULT_THRESHOLDS


# ---------- issues for VEDIX ----------

def test_smells_become_vedix_issues():
    project = make_project({"calc.py": CODE})
    validate_project(project)
    analyze_project(project, LOW_LIMITS)
    issues = static_to_issues(project)

    assert len(issues) == 7

    first = issues[0]  # Calculator.add: 2 parameters, limit 1
    assert first["file_path"] == "calc.py"
    assert first["line"] == 6
    assert first["severity"] == "low"
    assert first["category"] == "code_smell"
    assert first["title"] == "Too many parameters: Calculator.add"
    assert first["before"] == "    def add(self, a, b):"
    assert first["source"] == "static"
    assert first["rule"] == "too_many_parameters"
    assert "takes 2 parameters" in first["explanation"]
    assert first["suggestion"]

    assert issues[2]["severity"] == "medium"        # divide: 4 parameters, more than double 1
    assert issues[5]["category"] == "complexity"    # helper: high complexity
    assert issues[6]["line"] == 3                   # the class
    assert issues[6]["title"] == "Large class: Calculator"

    assert len({issue["id"] for issue in issues}) == 7
    for issue in issues:
        assert issue["severity"] in SEVERITIES
        assert issue["category"] in CATEGORIES


def test_no_issues_without_smells():
    project = make_project({"calc.py": CODE})
    validate_project(project)
    analyze_project(project)  # default thresholds
    assert static_to_issues(project) == []