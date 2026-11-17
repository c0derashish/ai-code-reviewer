import os
import re

# The ONE place that knows which languages VEDIX supports.
# Ids are lowercase and match the VEDIX frontend (Monaco editor ids).
LANGUAGES = {
    "python": {"name": "Python", "extensions": [".py"], "shebangs": ["python"]},
    "javascript": {
        "name": "JavaScript",
        "extensions": [".js", ".jsx", ".mjs", ".cjs"],
        "shebangs": ["node"],  # also matches "nodejs"
    },
    "typescript": {
        "name": "TypeScript",
        "extensions": [".ts", ".tsx"],
        "shebangs": ["ts-node"],
    },
    "java": {"name": "Java", "extensions": [".java"]},
    "c": {"name": "C", "extensions": [".c", ".h"]},  # ".h" is checked by content
    "cpp": {"name": "C++", "extensions": [".cpp", ".cc", ".cxx", ".hpp"]},
    "csharp": {"name": "C#", "extensions": [".cs"]},
    "go": {"name": "Go", "extensions": [".go"]},
    "rust": {"name": "Rust", "extensions": [".rs"]},
    "php": {"name": "PHP", "extensions": [".php"], "shebangs": ["php"]},
    "kotlin": {"name": "Kotlin", "extensions": [".kt"]},
}


def _build_extension_map() -> dict:
    mapping = {}
    for language_id, info in LANGUAGES.items():
        for extension in info["extensions"]:
            mapping[extension] = language_id
    return mapping


# ".js" -> "javascript"
EXTENSION_TO_LANGUAGE = _build_extension_map()

# Every file type VEDIX will read. input_manager imports this.
SOURCE_EXTENSIONS = set(EXTENSION_TO_LANGUAGE)

# Words that suggest a ".h" file is C++ and not C. This is a guess, not proof.
CPP_HINTS = [
    re.compile(pattern)
    for pattern in (
        r"\bclass\s+\w+",
        r"\bnamespace\s+\w+",
        r"\btemplate\s*<",
        r"\bstd::",
        r"#include\s*<(iostream|vector|string|map|memory|algorithm)>",
        r"\b(public|private|protected)\s*:",
    )
]


def get_language_name(language_id) -> str:
    if language_id in LANGUAGES:
        return LANGUAGES[language_id]["name"]
    return "Unknown"


def _get_extension(file_path: str) -> str:
    file_name = file_path.replace("\\", "/").split("/")[-1]
    return os.path.splitext(file_name)[1].lower()


def _get_shebang_language(source_code: str):
    """Look at a first line like '#!/usr/bin/env python3'."""
    first_line = source_code.split("\n", 1)[0].strip()
    if not first_line.startswith("#!"):
        return None

    parts = first_line[2:].split()
    if not parts:
        return None

    program = parts[0].split("/")[-1]
    if program == "env":
        # "env python3" or "env -S python3 -u": use the first word that is not an option
        words = [word for word in parts[1:] if not word.startswith("-")]
        if not words:
            return None
        program = words[0].split("/")[-1]

    for language_id, info in LANGUAGES.items():
        for name in info.get("shebangs", []):
            if program.startswith(name):
                return language_id
    return None


def _c_or_cpp(source_code: str) -> str:
    for pattern in CPP_HINTS:
        if pattern.search(source_code):
            return "cpp"
    return "c"


def _result(language, method, ambiguous) -> dict:
    return {"language": language, "method": method, "ambiguous": ambiguous}


def detect_language(file_path: str, source_code: str = "") -> dict:
    """Decide the language of one file.

    method says how we decided: "extension", "shebang", "content" or "unknown".
    ambiguous is True when the extension alone cannot decide (".h").
    language is None when we do not support the file.
    """
    extension = _get_extension(file_path)

    if extension == ".h":
        return _result(_c_or_cpp(source_code), "content", True)

    if extension in EXTENSION_TO_LANGUAGE:
        return _result(EXTENSION_TO_LANGUAGE[extension], "extension", False)

    shebang_language = _get_shebang_language(source_code)
    if shebang_language:
        return _result(shebang_language, "shebang", False)

    return _result(None, "unknown", False)


def count_nonblank_lines(source_code: str) -> int:
    return sum(1 for line in source_code.split("\n") if line.strip())


def detect_project_languages(project) -> dict:
    """Set file.language on every file and fill the project's language fields.

    Counting rule: a language's size is its number of NON-BLANK lines (comment
    lines included). Percentage = that language's lines / all lines * 100.
    If every line is blank, files are used instead of lines.
    Primary language = most lines. Tie: more files. Tie: alphabetical id.
    """
    stats = {}
    unknown_files = 0

    for code_file in project.files:
        result = detect_language(code_file.file_path, code_file.source_code)
        code_file.language = result["language"]

        language_id = result["language"]
        if language_id is None:
            unknown_files += 1
            continue

        if language_id not in stats:
            stats[language_id] = {
                "name": get_language_name(language_id),
                "files": 0,
                "lines": 0,
                "percentage": 0.0,
            }
        stats[language_id]["files"] += 1
        stats[language_id]["lines"] += count_nonblank_lines(code_file.source_code)

    total_lines = sum(entry["lines"] for entry in stats.values())
    total_files = sum(entry["files"] for entry in stats.values())

    for entry in stats.values():
        if total_lines > 0:
            share = entry["lines"] / total_lines
        elif total_files > 0:
            share = entry["files"] / total_files
        else:
            share = 0
        entry["percentage"] = round(share * 100, 1)

    # biggest first. This order is also the tie-breaking rule for "primary"
    ordered = dict(
        sorted(stats.items(), key=lambda item: (-item[1]["lines"], -item[1]["files"], item[0]))
    )

    primary = next(iter(ordered), None)
    project.detected_languages = ordered
    project.primary_language = primary

    return {
        "primary_language": primary,
        "primary_language_name": get_language_name(primary) if primary else None,
        "languages": ordered,
        "unknown_files": unknown_files,
    }