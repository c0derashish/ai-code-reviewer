import io
import tokenize

from analyzer.static.python_analyzer import split_lines

# Changes whenever the duplicate-code rules change. Saved with every result.
DUPLICATION_VERSION = "python-token-clones-0.1"

# Starting values. They are OUR choices, not standards.
DEFAULT_MIN_TOKENS = 50   # smallest clone, counted in tokens
DEFAULT_MIN_LINES = 5     # smallest clone, counted in lines (the smaller copy)
MIN_ALLOWED_TOKENS = 10

MAX_TOTAL_TOKENS = 500_000    # bigger projects are skipped
MAX_CLONES = 200              # we keep the biggest ones
MEDIUM_DUPLICATE_LINES = 20   # a copy this long is "medium" severity, else "low"

# Thrown away before comparing. Comments and blank lines do not matter.
IGNORED_TOKEN_TYPES = {tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER}
# Kept for comparing (so block structure counts), but ignored for line numbers.
STRUCTURE_TOKEN_TYPES = {tokenize.INDENT, tokenize.DEDENT}

# Numbers for the rolling hash
BASE = 1_000_003
MODULO = (1 << 61) - 1


def window_hashes(ids, size):
    """A hash for every run of `size` tokens.

    Each step drops the oldest token and adds the newest, so the cost does not
    depend on `size`.
    """
    if size <= 0 or len(ids) < size:
        return []

    top = pow(BASE, size - 1, MODULO)
    value = 0
    for number in ids[:size]:
        value = (value * BASE + number) % MODULO

    hashes = [value]
    for position in range(size, len(ids)):
        value = (value - ids[position - size] * top) % MODULO  # drop the oldest
        value = (value * BASE + ids[position]) % MODULO        # add the newest
        hashes.append(value)
    return hashes


def _token_key(token):
    """What we compare. Indentation style and line endings do not matter."""
    if token.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
        return (token.type, "")
    return (token.type, token.string)


def _read_tokens(source_code):
    """List of (key, start_line, end_line, is_real). None if the file cannot be tokenized."""
    tokens = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source_code).readline):
            if token.type in IGNORED_TOKEN_TYPES:
                continue
            is_real = token.type not in STRUCTURE_TOKEN_TYPES
            tokens.append((_token_key(token), token.start[0], token.end[0], is_real))
    except (tokenize.TokenError, SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    return tokens


def _load_files(project):
    """Tokenize every analysed Python file. Returns (files, unreadable_paths)."""
    key_ids = {}  # every different token gets a number
    files = []
    unreadable = []

    for code_file in project.files:
        result = code_file.analysis_result
        if code_file.language != "python" or not result or result["status"] != "analyzed":
            continue

        tokens = _read_tokens(code_file.source_code)
        if tokens is None:
            unreadable.append(code_file.file_path)
            continue

        files.append(
            {
                "file": code_file,
                "ids": [key_ids.setdefault(item[0], len(key_ids) + 1) for item in tokens],
                "starts": [item[1] for item in tokens],
                "ends": [item[2] for item in tokens],
                "real": [item[3] for item in tokens],
            }
        )
    return files, unreadable


def _find_runs(files, size):
    """Find token runs that appeared before.

    Each window is compared with the FIRST time that window was seen. So a block
    copied twice gives two clones, each paired with the original.
    Neighbouring matching windows are joined into one "run".
    """
    first_seen = {}  # window hash -> (file number, position)
    runs = []

    for b, file_b in enumerate(files):
        ids_b = file_b["ids"]
        run = None

        for i, value in enumerate(window_hashes(ids_b, size)):
            match = None
            found = first_seen.get(value)
            if found is not None:
                a, position = found
                # two different codes can rarely share a hash, so compare the tokens too
                if files[a]["ids"][position:position + size] == ids_b[i:i + size]:
                    match = found

            if match is None:
                first_seen.setdefault(value, (b, i))
                if run is not None:
                    runs.append(run)
                    run = None
                continue

            a, position = match
            continues_run = (
                run is not None
                and run["a"] == a
                and position == run["start_a"] + run["windows"]
                and i == run["start_b"] + run["windows"]
            )
            if continues_run:
                run["windows"] += 1
            else:
                if run is not None:
                    runs.append(run)
                run = {"a": a, "start_a": position, "b": b, "start_b": i, "windows": 1}

        if run is not None:
            runs.append(run)

    return runs


def _region(file_data, start, count):
    """Lines covered by `count` tokens starting at `start`."""
    spans = [
        (file_data["starts"][k], file_data["ends"][k])
        for k in range(start, start + count)
        if file_data["real"][k]
    ]
    if not spans:
        return None

    start_line = min(span[0] for span in spans)
    end_line = max(span[1] for span in spans)
    return {
        "file_path": file_data["file"].file_path,
        "start_line": start_line,
        "end_line": end_line,
        "lines": end_line - start_line + 1,
    }


def _runs_to_clones(files, runs, size, min_tokens, min_lines):
    clones = []

    for run in runs:
        tokens = run["windows"] + size - 1

        # Two copies in the same file must not overlap. If code repeats again and
        # again, we keep the first pair, so each copy is paired with the original.
        if run["a"] == run["b"]:
            tokens = min(tokens, run["start_b"] - run["start_a"])
        if tokens < min_tokens:
            continue

        first = _region(files[run["a"]], run["start_a"], tokens)
        second = _region(files[run["b"]], run["start_b"], tokens)
        if first is None or second is None:
            continue
        if min(first["lines"], second["lines"]) < min_lines:
            continue

        clones.append({"tokens": tokens, "first": first, "second": second})

    return clones


def _count_lines(files, clones):
    """Duplicated and total NON-BLANK lines for every file (comment lines included)."""
    info = {}
    for file_data in files:
        code_file = file_data["file"]
        lines = split_lines(code_file.source_code)
        info[code_file.file_path] = {
            "lines": lines,
            "total": sum(1 for line in lines if line.strip()),
            "duplicated": set(),
        }

    for clone in clones:
        for region in (clone["first"], clone["second"]):
            entry = info[region["file_path"]]
            for number in range(region["start_line"], region["end_line"] + 1):
                if 1 <= number <= len(entry["lines"]) and entry["lines"][number - 1].strip():
                    entry["duplicated"].add(number)

    return info


def _ratio(duplicated, total):
    return round(duplicated / total * 100, 1) if total > 0 else None


def find_duplicates(project, min_tokens=DEFAULT_MIN_TOKENS, min_lines=DEFAULT_MIN_LINES) -> dict:
    """Find exact duplicated code in the Python files of a project.

    Run analyze_project(project) first. Rules: research/methodology.md.
    Per-file numbers are saved in code_file.analysis_result["duplication"].
    """
    if min_tokens < MIN_ALLOWED_TOKENS or min_lines < 1:
        raise ValueError(
            f"min_tokens must be at least {MIN_ALLOWED_TOKENS} and min_lines at least 1."
        )

    report = {
        "status": "ok",
        "version": DUPLICATION_VERSION,
        "settings": {"min_tokens": min_tokens, "min_lines": min_lines},
        "note": None,
        "clones": [],
        "clone_count": 0,
        "truncated": False,
        "files_checked": 0,
        "files_unreadable": [],
        "duplicated_lines": 0,
        "total_lines": 0,
        "duplication_ratio": None,
        "files": {},
    }

    files, unreadable = _load_files(project)
    report["files_unreadable"] = unreadable
    report["files_checked"] = len(files)

    if not files:
        report["status"] = "skipped"
        report["note"] = "No Python files to check."
        return report

    total_tokens = sum(len(file_data["ids"]) for file_data in files)
    if total_tokens > MAX_TOTAL_TOKENS:
        report["status"] = "skipped"
        report["note"] = (
            f"The project is too large for the duplicate check (limit {MAX_TOTAL_TOKENS} tokens)."
        )
        return report

    runs = _find_runs(files, min_tokens)
    clones = _runs_to_clones(files, runs, min_tokens, min_tokens, min_lines)

    # biggest first. Keep at most MAX_CLONES
    clones.sort(key=lambda c: (-c["tokens"], c["second"]["file_path"], c["second"]["start_line"]))
    report["truncated"] = len(clones) > MAX_CLONES
    clones = clones[:MAX_CLONES]
    for number, clone in enumerate(clones, start=1):
        clone["id"] = number
    report["clones"] = clones
    report["clone_count"] = len(clones)

    # line counts, for every file and for the whole project
    info = _count_lines(files, clones)
    for file_data in files:
        code_file = file_data["file"]
        entry = info[code_file.file_path]
        duplicated = len(entry["duplicated"])
        per_file = {
            "duplicated_lines": duplicated,
            "total_lines": entry["total"],
            "ratio": _ratio(duplicated, entry["total"]),
        }
        report["files"][code_file.file_path] = per_file
        code_file.analysis_result["duplication"] = per_file
        report["duplicated_lines"] += duplicated
        report["total_lines"] += entry["total"]

    report["duplication_ratio"] = _ratio(report["duplicated_lines"], report["total_lines"])
    return report