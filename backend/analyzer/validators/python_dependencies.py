import ast
import sys

# Standard library module names of the Python that runs the server.
# (needs Python 3.10 or newer. You have 3.12.)
STANDARD_LIBRARY = set(sys.stdlib_module_names)


def build_known_modules(python_paths) -> set:
    """Every module name that exists inside the project, as dotted names.

    "pkg/mod.py" gives "pkg.mod" and also "pkg" (a folder can act as a package).
    "pkg/__init__.py" gives "pkg".
    """
    known = set()
    for path in python_paths:
        if not path.endswith(".py"):
            continue  # a script with no .py name cannot be imported
        parts = path[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for count in range(1, len(parts) + 1):
            known.add(".".join(parts[:count]))
    return known


def _classify(module_name, known_modules, local_tops):
    """Returns (group, missing). Local files win over the standard library,
    because Python looks in the project folder first."""
    top = module_name.split(".")[0]
    if top in local_tops:
        return "local", module_name not in known_modules
    if top in STANDARD_LIBRARY:
        return "standard_library", False
    return "external", False


def _resolve_relative(file_path, level, module):
    """Dotted name of a relative import, or None if it goes above the project."""
    package = file_path.split("/")[:-1]  # the folders the file is in
    if level - 1 > len(package):
        return None
    base = package[: len(package) - (level - 1)]
    return ".".join(base + module.split("."))


def _warning(error_type, message, file_path, node) -> dict:
    return {
        "type": error_type,
        "stage": "dependency",
        "severity": "warning",
        "file": file_path,
        "line": node.lineno,
        "column": node.col_offset + 1,
        "message": message,
    }


def check_dependencies(file_path, source_code, known_modules):
    """Look at the imports of one Python file.

    Returns (dependencies, errors).
    dependencies lists top-level names in three groups.
    errors holds a warning for each import that points inside the project but
    finds nothing. Packages from outside (like "requests") are only listed.
    We do NOT check that they exist or are installed.
    """
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None, []

    local_tops = {name.split(".")[0] for name in known_modules}
    groups = {"standard_library": set(), "local": set(), "external": set()}
    errors = []

    for node in ast.walk(tree):
        names = []  # module names written with a full path, like "pkg.mod"

        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module]
        elif isinstance(node, ast.ImportFrom) and node.module:
            # relative import such as "from .tools import x".
            # "from . import x" is skipped: x may be a name inside __init__.py.
            full_name = _resolve_relative(file_path, node.level, node.module)
            if full_name is None:
                errors.append(
                    _warning(
                        "RelativeImportError",
                        "This relative import goes above the project folder.",
                        file_path,
                        node,
                    )
                )
            elif full_name not in known_modules:
                errors.append(
                    _warning(
                        "MissingLocalModule",
                        f"Cannot find module '{full_name}' in the project.",
                        file_path,
                        node,
                    )
                )

        for name in names:
            group, missing = _classify(name, known_modules, local_tops)
            groups[group].add(name.split(".")[0])
            if missing:
                errors.append(
                    _warning(
                        "MissingLocalModule",
                        f"Cannot find module '{name}' in the project.",
                        file_path,
                        node,
                    )
                )

    errors.sort(key=lambda error: (error["line"], error["column"]))
    dependencies = {group: sorted(found) for group, found in groups.items()}
    return dependencies, errors