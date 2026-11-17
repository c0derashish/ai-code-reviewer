import csv
import json
import os
from collections import Counter

import pytest

from ai_engine.prompts import PROMPT_VERSION
from analyzer.static.integrations import tool_runner
from data_science.judging import (
    SHEET_COLUMNS,
    build_items,
    code_context,
    cohens_kappa,
    main,
    read_csv,
    sample_items,
    score_sheet,
    summarize,
    wilson_interval,
    write_files,
)
from input_manager import from_uploads
from services.pipeline import run_pipeline

SOURCE = "a\nb\nc\nd\ne\nf\n"

CODE = "\n".join([
    '"""Module doc."""',
    "",
    "class Calculator:",
    '    """A calculator."""',
    "",
    "    def add(self, a, b):",
    '        """Add two numbers."""',
    "        return a + b",
    "",
    "    def divide(self, a, b=1, *args, **kwargs):",
    "        if b == 0:",
    "            return None",
    "        return a / b",
    "",
    "",
    "def helper(x):",
    "    for i in x:",
    "        if i and i > 0:",
    "            print(i)",
    "",
])

LOW_LIMITS = {
    "long_method_lines": 3,
    "max_parameters": 1,
    "max_nesting_depth": 1,
    "max_complexity": 3,
    "large_class_lines": 10,
    "large_class_methods": 1,
}


@pytest.fixture(autouse=True)
def no_external_tools(monkeypatch):
    monkeypatch.setattr(tool_runner, "get_tool_version", lambda name: None)


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def complete(self, system, user):
        issue = {
            "line": 11, "code_quote": "if b == 0:", "severity": "medium",
            "category": "bug", "title": "Division check is incomplete",
            "explanation": "Only zero is handled.", "confidence": "high",
        }
        return json.dumps({"issues": [issue]})


def plain_items():
    items = []
    for number in range(12):
        items.append({"source": "static", "project_name": "p", "file_path": f"f{number}.py",
                      "line": number + 1, "title": "t"})
    for number in range(3):
        items.append({"source": "ai", "project_name": "p", "file_path": f"g{number}.py",
                      "line": 1, "title": "t"})
    items.append({"source": "ruff", "project_name": "p", "file_path": "h.py", "line": 1, "title": "t"})
    return items


def key_row(item_id, source, path, line):
    return {"item_id": item_id, "source": source, "rule": "", "model": "", "prompt_version": "",
            "project_name": "p", "file_path": path, "line": str(line), "severity": "low",
            "category": "bug"}


def sheet_row(item_id, path, line, correct="", useful="", severity_fit="", judge="j1"):
    return {"item_id": item_id, "file_path": path, "line": str(line), "correct": correct,
            "useful": useful, "severity_fit": severity_fit, "judge": judge, "notes": ""}


# ---------- code context ----------

def test_code_context():
    assert code_context(SOURCE, 4, radius=2) == "\n".join([
        "     2 | b",
        "     3 | c",
        ">    4 | d",
        "     5 | e",
        "     6 | f",
    ])


def test_code_context_edges():
    assert code_context(SOURCE, 1, radius=2) == "\n".join([
        ">    1 | a", "     2 | b", "     3 | c",
    ])
    assert code_context(SOURCE, 6, radius=2) == "\n".join([
        "     4 | d", "     5 | e", ">    6 | f",
    ])
    assert code_context(SOURCE, 99, radius=2) == code_context(SOURCE, 6, radius=2)
    assert code_context("x" * 300 + "\n", 1) == ">    1 | " + "x" * 200
    assert code_context("", 1) == ""


# ---------- building and sampling ----------

def test_build_items():
    project = from_uploads("demo", [("calc.py", CODE.encode()), ("bad.py", b"def broken(:\n")])
    result = run_pipeline(project, ai_provider=FakeProvider(), thresholds=LOW_LIMITS)

    items = build_items("demo", project, result)

    assert Counter(item["source"] for item in items) == {"validation": 1, "static": 7, "ai": 1}

    ai = next(item for item in items if item["source"] == "ai")
    assert ai["model"] == "fake-model"
    assert ai["prompt_version"] == PROMPT_VERSION
    assert ai["rule"] == "ai_review"
    assert (ai["file_path"], ai["line"]) == ("calc.py", 11)
    assert (ai["severity"], ai["category"]) == ("medium", "bug")
    assert ai["title"] == "Division check is incomplete"
    assert ">   11 | " in ai["code_context"]
    assert "if b == 0:" in ai["code_context"]

    validation = next(item for item in items if item["source"] == "validation")
    assert (validation["file_path"], validation["line"]) == ("bad.py", 1)
    assert validation["rule"] == ""
    assert validation["model"] == ""


def test_sampling_takes_up_to_n_per_source():
    chosen = sample_items(plain_items(), per_source=5, seed=0)

    assert Counter(item["source"] for item in chosen) == {"static": 5, "ai": 3, "ruff": 1}
    assert [item["item_id"] for item in chosen] == [f"J{n:04d}" for n in range(1, 10)]


def test_sampling_is_repeatable_and_leaves_the_input_alone():
    items = plain_items()

    first = sample_items(items, per_source=5, seed=7)
    again = sample_items(items, per_source=5, seed=7)
    reversed_input = sample_items(list(reversed(items)), per_source=5, seed=7)

    assert first == again
    assert first == reversed_input
    assert all("item_id" not in item for item in items)


# ---------- files ----------

def test_sheet_is_blind_and_round_trips(tmp_path):
    items = [{
        "source": "ai", "rule": "ai_review", "model": "m", "prompt_version": "p1",
        "project_name": "proj", "file_path": "a.py", "line": 3, "severity": "high",
        "category": "bug", "title": "Título é", "explanation": "two\nlines", "suggestion": "",
        "code_context": ">    3 | x\n     4 | y",
    }]
    chosen = sample_items(items, per_source=5, seed=0)

    sheet_path, key_path = write_files(chosen, str(tmp_path), force=False)

    assert os.path.basename(sheet_path) == "judging_sheet.csv"
    assert os.path.basename(key_path) == "judging_key.csv"

    sheet = read_csv(sheet_path)
    key = read_csv(key_path)
    assert list(sheet[0]) == SHEET_COLUMNS
    for hidden in ("source", "rule", "model", "prompt_version"):
        assert hidden not in sheet[0]
    assert sheet[0]["title"] == "Título é"
    assert sheet[0]["explanation"] == "two\nlines"
    assert sheet[0]["code_context"] == ">    3 | x\n     4 | y"
    assert sheet[0]["correct"] == ""
    assert sheet[0]["judge"] == ""

    assert key[0]["item_id"] == sheet[0]["item_id"] == "J0001"
    assert (key[0]["source"], key[0]["rule"], key[0]["model"]) == ("ai", "ai_review", "m")
    assert key[0]["prompt_version"] == "p1"


# ---------- statistics ----------

def test_wilson_interval():
    assert wilson_interval(0, 0) is None

    low, high = wilson_interval(8, 10)
    assert low == pytest.approx(0.490, abs=0.001)
    assert high == pytest.approx(0.943, abs=0.001)

    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert high == pytest.approx(0.2775, abs=0.001)

    low, high = wilson_interval(10, 10)
    assert low == pytest.approx(0.722, abs=0.001)
    assert high == 1.0


def test_kappa():
    first = dict(enumerate("yes yes yes no no no yes no yes no".split(), start=1))
    second = dict(enumerate("yes yes no no no yes yes no yes no".split(), start=1))
    # 8 of 10 agree (0.8). Each judge says yes 5 times: by chance 0.5. kappa = (0.8 - 0.5) / 0.5
    assert cohens_kappa(first, second) == pytest.approx(0.6)

    assert cohens_kappa({1: "yes", 2: "no"}, {1: "yes", 2: "no"}) == 1.0
    assert cohens_kappa({1: "yes", 2: "no"}, {1: "no", 2: "yes"}) == -1.0
    assert cohens_kappa({1: "yes", 2: "yes"}, {1: "yes", 2: "yes"}) is None  # one label only
    assert cohens_kappa({1: "yes"}, {2: "yes"}) is None                       # nothing in common
    assert cohens_kappa({1: "yes", 2: None}, {1: "yes", 2: "no"}) is None     # one common item, one label


def test_scoring_a_sheet():
    key = (
        [key_row(f"J000{n}", "ai", "a.py", 3) for n in range(1, 5)]
        + [key_row(f"J000{n}", "static", "b.py", 7) for n in range(5, 9)]
    )
    rows = [
        sheet_row("J0001", "a.py", 3, "yes", "yes", "right"),
        sheet_row("J0002", "a.py", 3, "yes", "no", "too_high"),
        sheet_row("J0003", "a.py", 3, "no", "yes", "right"),
        sheet_row("J0004", "a.py", 3, "unsure", "yes", ""),
        sheet_row("J0005", "b.py", 7, "yes", "yes", "right"),
        sheet_row("J0006", "b.py", 7, "yes", "yes", "right"),
        sheet_row("J0007", "b.py", 7, "yes", "no", "right"),
        sheet_row("J0008", "b.py", 7),  # not judged
    ]

    scored = score_sheet(rows, key)
    assert scored["problems"] == {
        "unknown_items": 0, "altered": 0, "duplicate_rows": 0, "invalid_answers": 0,
    }

    stats = summarize(scored["items"])
    assert list(stats) == ["ai", "static"]

    ai = stats["ai"]
    assert (ai["n_items"], ai["n_judged"]) == (4, 4)
    assert (ai["correct_yes"], ai["correct_no"], ai["correct_unsure"]) == (2, 1, 1)
    assert ai["correct_rate"] == 0.5
    assert ai["correct_ci_low"] == pytest.approx(0.150, abs=0.001)
    assert ai["correct_ci_high"] == pytest.approx(0.850, abs=0.001)
    assert ai["precision_without_unsure"] == 0.667
    assert (ai["useful_n"], ai["useful_yes"], ai["useful_rate"]) == (4, 3, 0.75)
    assert (ai["severity_n"], ai["severity_right"], ai["severity_too_high"], ai["severity_too_low"]) == (3, 2, 1, 0)

    static = stats["static"]
    assert (static["n_items"], static["n_judged"]) == (4, 3)  # one row was left blank
    assert static["correct_rate"] == 1.0
    assert static["correct_ci_low"] == pytest.approx(0.438, abs=0.001)
    assert static["correct_ci_high"] == 1.0
    assert (static["useful_n"], static["useful_yes"], static["useful_rate"]) == (3, 2, 0.667)
    assert static["severity_right"] == 3


def test_scoring_counts_problems_and_ignores_bad_rows():
    key = [key_row("J0001", "ai", "a.py", 3), key_row("J0002", "ai", "a.py", 4),
           key_row("J0003", "ai", "a.py", 5)]
    rows = [
        sheet_row("J0001", "a.py", 3, "yes", "yes", "right"),
        sheet_row("J0001", "a.py", 3, "no", "no", "right"),           # the same id again
        sheet_row("J9999", "a.py", 3, "yes"),                         # not in the key
        sheet_row("J0002", "other.py", 4, "yes"),                     # file changed
        sheet_row("J0003", "a.py", 5, "maybe", "YES", "too high"),    # one invalid answer
    ]

    scored = score_sheet(rows, key)

    assert scored["problems"] == {
        "unknown_items": 1, "altered": 1, "duplicate_rows": 1, "invalid_answers": 1,
    }
    assert [item["item_id"] for item in scored["items"]] == ["J0001", "J0003"]
    third = scored["items"][1]
    assert third["correct"] is None
    assert third["useful"] == "yes"
    assert third["severity_fit"] == "too_high"


# ---------- the commands ----------

def test_export_and_score_end_to_end(tmp_path, capsys):
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    out = tmp_path / "judging"

    assert main(["export", str(folder), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "Sampled 1 findings: validation 1" in printed
    assert "--ai was not given" in printed

    sheet_path = out / "judging_sheet.csv"
    key_path = out / "judging_key.csv"
    rows = read_csv(sheet_path)
    assert len(rows) == 1
    assert rows[0]["item_id"] == "J0001"
    assert rows[0]["title"] == "Syntax error"
    assert rows[0]["file_path"] == "bad.py"

    rows[0].update(correct="yes", useful="yes", severity_fit="right", judge="tester")
    filled = tmp_path / "filled.csv"
    with open(filled, "w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    scores = tmp_path / "scores.csv"
    code = main(["score", str(filled), "--key", str(key_path), "--out", str(scores)])
    assert code == 0

    printed = capsys.readouterr().out
    assert "validation" in printed
    assert "judge: tester" in printed

    result = read_csv(scores)
    assert len(result) == 1
    assert result[0]["source"] == "validation"
    assert result[0]["correct_rate"] == "1.0"
    assert result[0]["n_judged"] == "1"


def test_export_does_not_overwrite_a_sheet(tmp_path, capsys):
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    out = tmp_path / "judging"

    assert main(["export", str(folder), "--out", str(out)]) == 0
    capsys.readouterr()

    assert main(["export", str(folder), "--out", str(out)]) == 1
    assert "already exists" in capsys.readouterr().out

    assert main(["export", str(folder), "--out", str(out), "--force"]) == 0