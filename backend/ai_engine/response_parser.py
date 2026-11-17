import json

from analyzer.findings import CATEGORIES, SEVERITIES

MAX_TITLE = 120
MAX_EXPLANATION = 1200
MAX_WHY = 500
MAX_SUGGESTION = 800
MAX_CODE = 3000
MAX_RANGE_LINES = 20
MAX_ISSUES_PER_FILE = 15
MAX_RAW_ISSUES = 100
MIN_QUOTE_LENGTH = 3

CONFIDENCES = ["low", "medium", "high"]


class ParseError(Exception):
    """The AI answer is not in the expected shape."""


def extract_issues(text) -> list:
    """Find the JSON object in the answer and return its "issues" list."""
    if not isinstance(text, str):
        raise ParseError("The answer is not text.")

    # models sometimes add ```json fences or a sentence before the JSON
    start = text.find("{")
    if start == -1:
        raise ParseError("The answer has no JSON.")

    try:
        # raw_decode reads one JSON object and ignores text after it
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        raise ParseError("The answer is not valid JSON.") from None

    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        raise ParseError("The answer has no 'issues' list.")
    return data["issues"]


def _normalize(text) -> str:
    return " ".join(str(text).split())


def verify_line(line, quote, lines):
    """Check that the quoted code really is on that line.

    Returns (line_number, moved) or None when the line cannot be verified.
    moved is True when the model's line number was wrong but the quote is in
    exactly one place, so we use that place.
    """
    if not isinstance(quote, str):
        return None

    # use the first non-empty part of the quote
    wanted = ""
    for part in quote.splitlines():
        if part.strip():
            wanted = _normalize(part)
            break
    if len(wanted) < MIN_QUOTE_LENGTH:
        return None

    if isinstance(line, int) and not isinstance(line, bool) and 1 <= line <= len(lines):
        if wanted in _normalize(lines[line - 1]):
            return line, False

    matches = [n for n, text in enumerate(lines, start=1) if wanted in _normalize(text)]
    if len(matches) == 1:
        return matches[0], True
    return None


def _text(value, limit) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _end_line(value, line, total, moved):
    if moved or isinstance(value, bool) or not isinstance(value, int):
        return None
    if line < value <= min(total, line + MAX_RANGE_LINES - 1):
        return value
    return None


def clean_issue(raw, file_path, lines):
    """One raw AI issue -> our finding. Returns (finding, None) or (None, reason).

    reason is "bad_format" or "unverified_line".
    """
    if not isinstance(raw, dict):
        return None, "bad_format"

    title = _text(raw.get("title"), MAX_TITLE)
    explanation = _text(raw.get("explanation"), MAX_EXPLANATION)
    if not title or not explanation:
        return None, "bad_format"

    verified = verify_line(raw.get("line"), raw.get("code_quote"), lines)
    if verified is None:
        return None, "unverified_line"
    line, moved = verified

    severity = str(raw.get("severity", "")).strip().lower()
    if severity == "critical":
        severity = "high"  # an AI cannot confirm a vulnerability
    if severity not in SEVERITIES:
        severity = "low"

    category = str(raw.get("category", "")).strip().lower()
    if category not in CATEGORIES:
        category = "code_smell"

    confidence = str(raw.get("confidence", "")).strip().lower()
    if confidence not in CONFIDENCES:
        confidence = "low"

    return {
        "file_path": file_path,
        "line": line,
        "end_line": _end_line(raw.get("end_line"), line, len(lines), moved),
        "severity": severity,
        "category": category,
        "title": title,
        "explanation": explanation,
        "why_it_matters": _text(raw.get("why_it_matters"), MAX_WHY),
        "suggestion": _text(raw.get("suggestion"), MAX_SUGGESTION),
        "refactored_code": _text(raw.get("refactored_code"), MAX_CODE) or None,
        "confidence": confidence,
        "line_moved": moved,
    }, None


def clean_issues(raw_issues, file_path, lines, existing_issues=None):
    """Clean every raw issue of one file. Returns (findings, dropped_counts).

    An issue is dropped when its format is wrong, its line cannot be verified,
    or it repeats an issue we already have (same file, line and category).
    """
    dropped = {"bad_format": 0, "unverified_line": 0, "duplicate": 0, "too_many": 0}
    seen = {(i["file_path"], i["line"], i["category"]) for i in (existing_issues or [])}

    raw_issues = raw_issues[:MAX_RAW_ISSUES]
    findings = []

    for index, raw in enumerate(raw_issues):
        if len(findings) >= MAX_ISSUES_PER_FILE:
            dropped["too_many"] = len(raw_issues) - index
            break

        finding, reason = clean_issue(raw, file_path, lines)
        if finding is None:
            dropped[reason] += 1
            continue

        key = (file_path, finding["line"], finding["category"])
        if key in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(key)
        findings.append(finding)

    return findings, dropped