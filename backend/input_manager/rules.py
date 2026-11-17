import os
import re

# Limits. Same numbers as the VEDIX frontend. The backend checks again
# because the browser cannot be trusted.
MAX_FILE_BYTES = 2 * 1024 * 1024        # one file
MAX_FILES = 500                          # source files in one project
MAX_TOTAL_BYTES = 25 * 1024 * 1024       # all accepted files together
MAX_SCANNED_ENTRIES = 20000              # local folders only: files we look at
MAX_PATH_LENGTH = 300
MAX_NAME_LENGTH = 100
MAX_SKIPPED_LISTED = 200                 # how many skipped files we list by name

# Generated or tool folders. We never go inside them.
IGNORED_FOLDERS = {
    "node_modules", ".git", ".hg", ".svn",
    "dist", "build", "target", "out_build",
    "__pycache__", "__macosx",
    "venv", ".venv",
    ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".next",
}

# Files we are willing to read. Phase 2 will make the language detector the
# single place that knows this list, and this will import from it.
SOURCE_EXTENSIONS = {
    ".py", ".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".go", ".rs", ".php", ".cs", ".kt",
}


def get_extension(path: str) -> str:
    return os.path.splitext(path)[1].lower()


def clean_path(raw_path):
    """Make a path safe. Returns (clean_path, None) or (None, reason).

    Rules: use "/" only, no absolute paths, no "..", no control characters.
    This stops a file called "../../x.py" from reaching outside the project.
    """
    if not isinstance(raw_path, str):
        return None, "invalid path"

    text = raw_path.strip()
    if text == "":
        return None, "empty path"
    if any(ord(char) < 32 for char in text):
        return None, "invalid characters in path"

    text = text.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return None, "absolute path"

    # drop empty parts and "." parts:  "./a//b.py" -> "a/b.py"
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts:
        return None, "empty path"
    if ".." in parts:
        return None, "path goes outside the project"

    clean = "/".join(parts)
    if len(clean) > MAX_PATH_LENGTH:
        return None, "path is too long"
    return clean, None


def clean_project_name(name) -> str:
    text = "".join(char for char in str(name) if ord(char) >= 32).strip()
    return text[:MAX_NAME_LENGTH] or "project"


def size_problem(size: int):
    """Returns a reason if a file of this size cannot be used, else None."""
    if size == 0:
        return "empty file"
    if size > MAX_FILE_BYTES:
        return f"larger than {MAX_FILE_BYTES // 1024} KB"
    return None