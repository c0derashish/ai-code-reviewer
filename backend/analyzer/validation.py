from analyzer.languages import get_language_name
from analyzer.validators.python_dependencies import build_known_modules, check_dependencies
from analyzer.validators.python_validator import PythonValidator

# One validator per language id. More are added in later phases.
VALIDATORS = {
    "python": PythonValidator(),
}


def _not_checked(language_id, note) -> dict:
    return {
        "status": "not_checked",
        "valid": None,  # None means "we do not know". It is NOT the same as valid
        "language": language_id,
        "errors": [],
        "dependencies": None,
        "note": note,
    }


def validate_file(code_file, known_modules) -> dict:
    language_id = code_file.language

    if language_id is None:
        return _not_checked(None, "Language not recognized, so the file was not checked.")

    validator = VALIDATORS.get(language_id)
    if validator is None:
        name = get_language_name(language_id)
        return _not_checked(language_id, f"No {name} validator yet, so the file was not checked.")

    result = validator.validate(code_file.source_code, code_file.file_path)
    errors = list(result["errors"])
    dependencies = None

    # The dependency check needs code that Python can read
    if result["valid"] and language_id == "python":
        dependencies, dependency_errors = check_dependencies(
            code_file.file_path, code_file.source_code, known_modules
        )
        errors.extend(dependency_errors)

    # warnings (like a missing import) do not make a file invalid
    has_error = any(error["severity"] == "error" for error in errors)

    return {
        "status": "invalid" if has_error else "valid",
        "valid": not has_error,
        "language": language_id,
        "errors": errors,
        "dependencies": dependencies,
        "note": None,
    }


def validate_project(project) -> dict:
    """Validate every file. Run detect_project_languages(project) first.

    The result of each file is stored in code_file.validation_result.
    Returns a count summary.
    """
    python_paths = [f.file_path for f in project.files if f.language == "python"]
    known_modules = build_known_modules(python_paths)

    summary = {
        "files": 0,
        "valid": 0,
        "invalid": 0,
        "not_checked": 0,
        "errors": 0,
        "warnings": 0,
    }

    for code_file in project.files:
        result = validate_file(code_file, known_modules)
        code_file.validation_result = result

        summary["files"] += 1
        summary[result["status"]] += 1
        for error in result["errors"]:
            if error["severity"] == "error":
                summary["errors"] += 1
            else:
                summary["warnings"] += 1

    return summary