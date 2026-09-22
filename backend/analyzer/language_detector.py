from pathlib import Path
from collections import defaultdict


LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".kt": "Kotlin",
}


IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
}


def detect_language_from_extension(file_path):
    """
    Detect language using file extension.
    """

    extension = Path(file_path).suffix.lower()

    return LANGUAGE_EXTENSIONS.get(extension)


def count_lines(file_path):
    """
    Count lines in a source file.
    """

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:

            return sum(1 for _ in file)

    except (OSError, UnicodeDecodeError):
        return 0


def scan_repository(repo_path):
    """
    Scan repository and collect language statistics.
    """

    repo_path = Path(repo_path)

    language_data = defaultdict(
        lambda: {
            "files": 0,
            "lines": 0
        }
    )

    for file_path in repo_path.rglob("*"):

        # Skip directories
        if not file_path.is_file():
            continue

        # Skip ignored directories
        if any(
            directory in file_path.parts
            for directory in IGNORED_DIRECTORIES
        ):
            continue

        language = detect_language_from_extension(file_path)

        if language is None:
            continue

        lines = count_lines(file_path)

        language_data[language]["files"] += 1
        language_data[language]["lines"] += lines

    return language_data


def calculate_language_percentages(language_data):
    """
    Calculate percentage of code based on lines of code.
    """

    total_lines = sum(
        data["lines"]
        for data in language_data.values()
    )

    if total_lines == 0:
        return {}

    result = {}

    for language, data in language_data.items():

        percentage = (
            data["lines"] / total_lines
        ) * 100

        result[language] = {
            "files": data["files"],
            "lines": data["lines"],
            "percentage": round(percentage, 2)
        }

    return result


def detect_repository_languages(repo_path):
    """
    Main repository language detection function.
    """

    raw_data = scan_repository(repo_path)

    language_data = calculate_language_percentages(
        raw_data
    )

    if not language_data:
        return {
            "primary_language": None,
            "languages": {}
        }

    primary_language = max(
        language_data,
        key=lambda language:
        language_data[language]["lines"]
    )

    return {
        "primary_language": primary_language,
        "languages": language_data
    }