from analyzer.static.python.function_analyzer import has_docstring


def measure_documentation(tree, functions, classes) -> dict:
    """Documentation coverage.

    Formula: coverage_percent = documented / total * 100, where
      total      = number of functions (methods included) + number of classes
      documented = how many of them have a non-empty docstring
    The module docstring is reported separately and is NOT in the formula.
    If there is nothing to document, coverage_percent is None (not 0).
    """
    functions_documented = sum(1 for function in functions if function["has_docstring"])
    classes_documented = sum(1 for one_class in classes if one_class["has_docstring"])

    total = len(functions) + len(classes)
    documented = functions_documented + classes_documented

    coverage = round(documented / total * 100, 1) if total > 0 else None

    return {
        "module_docstring": has_docstring(tree),
        "functions": {"documented": functions_documented, "total": len(functions)},
        "classes": {"documented": classes_documented, "total": len(classes)},
        "coverage_percent": coverage,
    }