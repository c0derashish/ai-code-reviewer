from analyzer.static.python_analyzer import split_lines
from analyzer.static.duplication import MEDIUM_DUPLICATE_LINES

# The values VEDIX accepts. See docs/API_CONTRACT.md in the frontend.
SEVERITIES = ["critical", "high", "medium", "low", "info"]
CATEGORIES = [
    "security", "bug", "complexity", "maintainability",
    "code_smell", "performance", "style",
]

MAX_BEFORE_LENGTH = 400

# stage -> (severity, category, title, explanation start, suggestion)
STAGE_TEXT = {
    "syntax": (
        "high",
        "bug",
        "Syntax error",
        "Python cannot read this code.",
        "Fix this first, because other checks need code Python can read. "
        "The real cause can be on an earlier line.",
    ),
    "compile": (
        "high",
        "bug",
        "Code cannot be compiled",
        "The syntax is fine, but Python refuses to compile the program.",
        "Fix this first, because other checks need code Python accepts.",
    ),
    "dependency": (
        "medium",
        "bug",
        "Import cannot be resolved",
        "",
        "Check the module name and the file path, or add the missing file.",
    ),
}


def _clamp_line(line, lines) -> int:
    """VEDIX needs a line between 1 and the last line of the file."""
    if not lines:
        return 1
    if not isinstance(line, int) or line < 1:
        return 1
    return min(line, len(lines))


def _make_issue(number, file_path, lines, error) -> dict:
    severity, category, title, start, suggestion = STAGE_TEXT[error["stage"]]
    line = _clamp_line(error.get("line"), lines)

    explanation = f"{start} {error['message']}".strip()
    before = lines[line - 1][:MAX_BEFORE_LENGTH] if lines else ""

    return {
        "id": f"validation-{number}",
        "file_path": file_path,
        "line": line,
        "severity": severity,
        "category": category,
        "title": title,
        "explanation": explanation,
        "suggestion": suggestion,
        "before": before,
    }


def validation_to_issues(project) -> list:
    """Turn validation errors into issues in the shape VEDIX expects."""
    issues = []

    for code_file in project.files:
        result = code_file.validation_result
        if not result:
            continue  # this file was not validated

        lines = split_lines(code_file.source_code)
        for error in result["errors"]:
            issues.append(_make_issue(len(issues) + 1, code_file.file_path, lines, error))

    return issues


# ---------- static analysis findings (Phase 4) ----------

# rule -> (category, title, why it matters, suggestion)
SMELL_TEXT = {
    "long_method": (
        "code_smell",
        "Long method",
        "Long functions are harder to read, test and change.",
        "Split the function into smaller functions that each do one job.",
    ),
    "too_many_parameters": (
        "code_smell",
        "Too many parameters",
        "A function with many parameters is easy to call wrongly and often does too much.",
        "Group related values in one object or dictionary, or split the function.",
    ),
    "deep_nesting": (
        "complexity",
        "Deep nesting",
        "Deeply nested code is hard to follow, because the reader must remember many conditions.",
        "Return early, or move the inner block into its own function.",
    ),
    "high_complexity": (
        "complexity",
        "High complexity",
        "Many decision points mean many paths to understand and to test.",
        "Split the function and simplify its conditions.",
    ),
    "large_class": (
        "code_smell",
        "Large class",
        "A very large class often has more than one responsibility.",
        "Move related methods into smaller classes.",
    ),
}


def _smell_severity(smell) -> str:
    # Our own simple rule: more than double the limit is "medium", otherwise "low".
    # A smell is a hint about maintainability. It is not a confirmed bug.
    if smell["value"] > 2 * smell["threshold"]:
        return "medium"
    return "low"


def static_to_issues(project) -> list:
    """Turn code smells into issues in the shape VEDIX expects."""
    issues = []

    for code_file in project.files:
        result = code_file.analysis_result
        if not result or result["status"] != "analyzed":
            continue

        lines = split_lines(code_file.source_code)
        for smell in result["smells"]:
            category, title, why, suggestion = SMELL_TEXT[smell["rule"]]
            line = _clamp_line(smell["line"], lines)

            issues.append(
                {
                    "id": f"static-{len(issues) + 1}",
                    "file_path": code_file.file_path,
                    "line": line,
                    "severity": _smell_severity(smell),
                    "category": category,
                    "title": f"{title}: {smell['target']}",
                    "explanation": f"{smell['message']} {why}",
                    "suggestion": suggestion,
                    "before": lines[line - 1][:MAX_BEFORE_LENGTH] if lines else "",
                    # extra fields. VEDIX ignores them. Needed later for the data analysis
                    "source": "static",
                    "rule": smell["rule"],
                }
            )

    return issues



# ---------- findings from Ruff and Bandit (Phase 4b) ----------

# Ruff rule -> (category, severity, title, why it matters, suggestion)
# These choices are ours. They are not from Ruff.
RUFF_TEXT = {
    "F401": (
        "maintainability", "low", "Unused import",
        "An import that is never used adds noise and can hide what the file really needs.",
        "Remove the import, or use it.",
    ),
    "F841": (
        "maintainability", "low", "Unused variable",
        "A value that is stored and never read is usually leftover code or a mistake.",
        "Remove the variable, or use its value.",
    ),
    "F811": (
        "bug", "medium", "Name defined twice",
        "The first definition is never used and the second silently replaces it.",
        "Rename one of them, or remove the one you do not need.",
    ),
    "F821": (
        "bug", "high", "Undefined name",
        "Python will raise NameError when this line runs, unless the name is added in an unusual way.",
        "Define or import the name, or fix its spelling.",
    ),
    "F632": (
        "bug", "medium", "Comparing a literal with 'is'",
        "'is' checks identity, not equality, so the result can be wrong for strings and numbers.",
        "Use '==' or '!=' to compare values.",
    ),
    "F403": (
        "maintainability", "low", "Star import",
        "'from module import *' hides where names come from and can overwrite names.",
        "Import only the names you need.",
    ),
    "F405": (
        "maintainability", "low", "Name may come from a star import",
        "Ruff cannot tell if this name exists, because it may come from 'import *'.",
        "Import the names explicitly.",
    ),
}

# any other Ruff rule
RUFF_DEFAULT = (
    "code_smell", "low", None,
    "Ruff reports a possible problem on this line.",
    "Read the message, then fix the line or ignore it if it is intended.",
)

# Bandit severity -> our severity. A tool cannot confirm a vulnerability,
# so nothing from Bandit is ever "critical".
BANDIT_SEVERITY = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}


def _ruff_fields(finding) -> dict:
    category, severity, title, why, suggestion = RUFF_TEXT.get(finding["rule"], RUFF_DEFAULT)
    return {
        "severity": severity,
        "category": category,
        "title": title or f"Ruff {finding['rule']}",
        "explanation": f"{finding['message']} {why}".strip(),
        "suggestion": suggestion,
    }


def _bandit_fields(finding) -> dict:
    name = finding["name"].replace("_", " ").capitalize() or "Security finding"
    confidence = finding["confidence"].lower() or "unknown"

    explanation = f"{finding['message']} Bandit confidence: {confidence}."
    if finding["cwe"]:
        explanation += f" (CWE-{finding['cwe']})"
    explanation += " This is a possible risk, not a confirmed vulnerability."

    return {
        "severity": BANDIT_SEVERITY.get(finding["severity"], "low"),
        "category": "security",
        "title": f"{name} ({finding['rule']})",
        "explanation": explanation,
        "suggestion": (
            "Check whether an outside user can control the input here. If so, use a "
            "safer alternative. Look up this check number in the Bandit documentation."
        ),
        "confidence": finding["confidence"],
    }


def tool_to_issues(project) -> list:
    """Turn Ruff and Bandit findings into issues in the shape VEDIX expects."""
    issues = []

    for code_file in project.files:
        result = code_file.analysis_result
        if not result or result.get("status") != "analyzed":
            continue

        lines = split_lines(code_file.source_code)
        for finding in result.get("tool_findings", []):
            if finding["source"] == "ruff":
                fields = _ruff_fields(finding)
            elif finding["source"] == "bandit":
                fields = _bandit_fields(finding)
            else:
                continue

            line = _clamp_line(finding["line"], lines)
            issue = {
                "id": f"tool-{len(issues) + 1}",
                "file_path": code_file.file_path,
                "line": line,
                "before": lines[line - 1][:MAX_BEFORE_LENGTH] if lines else "",
                "source": finding["source"],
                "rule": finding["rule"],
            }
            issue.update(fields)
            issues.append(issue)

    return issues


# ---------- duplicate code findings (Phase 4c) ----------

def duplication_to_issues(project, report) -> list:
    """One issue per clone, placed on the copy (the later one).

    The explanation names the other location. VEDIX has no field for a
    second location, so it goes into the text.
    """
    issues = []

    for clone in report.get("clones", []):
        first = clone["first"]
        second = clone["second"]

        code_file = project.get_file(second["file_path"])
        if code_file is None:
            continue

        lines = split_lines(code_file.source_code)
        line = _clamp_line(second["start_line"], lines)
        severity = "medium" if second["lines"] >= MEDIUM_DUPLICATE_LINES else "low"

        issues.append(
            {
                "id": f"duplicate-{len(issues) + 1}",
                "file_path": second["file_path"],
                "line": line,
                "severity": severity,
                "category": "code_smell",
                "title": f"Duplicate code ({second['lines']} lines)",
                "explanation": (
                    f"Lines {second['start_line']}-{second['end_line']} repeat lines "
                    f"{first['start_line']}-{first['end_line']} of {first['file_path']} "
                    "(comments, blank lines and spacing are ignored). "
                    "Every fix or change must be made in each copy."
                ),
                "suggestion": (
                    "Move the shared code into one function and call it from both places."
                ),
                "before": lines[line - 1][:MAX_BEFORE_LENGTH] if lines else "",
                "source": "duplication",
                "rule": "duplicate_code",
                "related": first,  # extra field. VEDIX ignores it
            }
        )

    return issues


# ---------- AI review findings (Phase 6) ----------

def ai_to_issues(project, report) -> list:
    """Turn the AI review report into issues in the shape VEDIX expects.

    "before" is taken from the real file, never from the AI answer.
    "after" is the AI's suggested code. It is a suggestion and is not checked.
    """
    issues = []

    for finding in report.get("findings", []):
        code_file = project.get_file(finding["file_path"])
        if code_file is None:
            continue

        lines = split_lines(code_file.source_code)
        line = _clamp_line(finding["line"], lines)
        end_line = finding["end_line"] or line

        explanation = finding["explanation"]
        if finding["why_it_matters"]:
            explanation += f" Why it matters: {finding['why_it_matters']}"
        explanation += (
            f" (AI review, confidence: {finding['confidence']}. "
            "A possible issue, not a confirmed one.)"
        )

        issues.append(
            {
                "id": f"ai-{len(issues) + 1}",
                "file_path": finding["file_path"],
                "line": line,
                "severity": finding["severity"],
                "category": finding["category"],
                "title": finding["title"],
                "explanation": explanation,
                "suggestion": finding["suggestion"],
                "before": "\n".join(lines[line - 1:end_line])[:800],
                "after": finding["refactored_code"],
                # extra fields. VEDIX ignores them. Needed for the data analysis later
                "source": "ai",
                "rule": "ai_review",
                "confidence": finding["confidence"],
                "line_moved": finding["line_moved"],
                "model": report.get("model"),
            }
        )

    return issues