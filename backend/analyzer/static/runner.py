import ast

from analyzer.static.python.code_smells import find_smells, get_thresholds
from analyzer.static.python.documentation import measure_documentation
from analyzer.static.python.function_analyzer import collect_structure, summarize_functions
from analyzer.static.python_analyzer import PythonAnalyzer

# Changes whenever a metric rule changes. Saved with every result (needed for research).
METRICS_VERSION = "python-static-0.1"

NOTE_ONLY_PYTHON = "Static analysis is only available for Python files so far."
NOTE_NOT_VALIDATED = "File has not been validated, so it was not analysed."
NOTE_HAS_ERRORS = "File has errors that must be fixed before it can be analysed."
NOTE_CANNOT_PARSE = "Python could not read this file, so it was not analysed."


def analyze_python_code(code, thresholds=None) -> dict:
    """Analyse valid Python code. Raises SyntaxError if the code cannot be parsed."""
    limits = get_thresholds(thresholds)
    tree = ast.parse(code)
    functions, classes = collect_structure(tree)

    return {
        "status": "analyzed",
        "metrics_version": METRICS_VERSION,
        "thresholds": limits,
        "metrics": PythonAnalyzer(code).analyze(),
        "functions": functions,
        "classes": classes,
        "function_summary": summarize_functions(functions),
        "documentation": measure_documentation(tree, functions, classes),
        "smells": find_smells(functions, classes, limits),
        "note": None,
    }


def _not_analyzed(note) -> dict:
    return {"status": "not_analyzed", "note": note}


def _analyze_file(code_file, thresholds) -> dict:
    if code_file.language != "python":
        return _not_analyzed(NOTE_ONLY_PYTHON)

    validation = code_file.validation_result
    if validation is None:
        return _not_analyzed(NOTE_NOT_VALIDATED)
    if validation["status"] != "valid":
        return _not_analyzed(NOTE_HAS_ERRORS)

    try:
        return analyze_python_code(code_file.source_code, thresholds)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return _not_analyzed(NOTE_CANNOT_PARSE)


def analyze_project(project, thresholds=None) -> dict:
    """Analyse every valid Python file. Run detect_project_languages and
    validate_project first. Each result is stored in code_file.analysis_result.
    Returns a count summary.
    """
    get_thresholds(thresholds)  # a typo in a threshold name fails here, before any work

    summary = {"analyzed": 0, "not_analyzed": 0, "smells": 0}

    for code_file in project.files:
        result = _analyze_file(code_file, thresholds)
        code_file.analysis_result = result

        if result["status"] == "analyzed":
            summary["analyzed"] += 1
            summary["smells"] += len(result["smells"])
        else:
            summary["not_analyzed"] += 1

    return summary