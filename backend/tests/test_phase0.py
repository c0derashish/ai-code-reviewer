from analyzer.static.python_analyzer import PythonAnalyzer, split_lines
from analyzer.validators.python_validator import PythonValidator


def validate(code, file_path="<unknown>"):
    return PythonValidator().validate(code, file_path)


def analyze(code):
    return PythonAnalyzer(code).analyze()


# ---------- validator ----------

def test_valid_code_passes():
    result = validate("x = 1\n")
    assert result["valid"] is True
    assert result["errors"] == []


def test_syntax_error_is_reported():
    result = validate("def broken(:\n    pass\n")
    error = result["errors"][0]
    assert result["valid"] is False
    assert error["type"] == "SyntaxError"
    assert error["line"] == 1


def test_indentation_error_keeps_its_real_name():
    result = validate("if True:\npass\n")
    assert result["errors"][0]["type"] == "IndentationError"


def test_return_outside_function_is_caught():
    result = validate("return 1\n")
    assert result["valid"] is False
    assert "return" in result["errors"][0]["message"]


def test_null_byte_does_not_crash():
    result = validate("x = 1\0")
    assert result["valid"] is False
    assert len(result["errors"]) == 1


def test_file_path_is_in_the_error():
    result = validate("x = (", "app.py")
    assert result["errors"][0]["file"] == "app.py"


def test_validator_does_not_run_code():
    # If this code ran, it would raise an error and fail the test.
    result = validate('raise RuntimeError("must not run")\n')
    assert result["valid"] is True


# ---------- analyzer ----------

def test_split_lines():
    assert split_lines("") == []
    assert split_lines("a\n") == ["a"]
    assert split_lines("a\nb") == ["a", "b"]
    assert split_lines("a\r\nb\r\n") == ["a", "b"]
    assert split_lines("a\x0cb\n") == ["a\x0cb"]  # form feed is not a line end


def test_line_counts():
    code = "import os, sys\n\n# a comment\ndef add(a, b):\n    return a + b\n"
    result = analyze(code)
    assert result["total_lines"] == 5
    assert result["blank_lines"] == 1
    assert result["comment_lines"] == 1
    assert result["code_lines"] == 3
    assert result["lines_of_code"] == 3
    assert result["functions"] == 1
    assert result["imports"] == 2
    assert result["variables"] == 0
    assert result["cyclomatic_complexity"] == 1
    assert result["max_nesting_depth"] == 0


def test_variable_names_counted_once():
    code = "x = y = 1\nx = 2\nfor i in range(3):\n    z = i\n"
    result = analyze(code)
    assert result["variables"] == 4  # x, y, i, z
    assert result["cyclomatic_complexity"] == 2  # the for loop


def test_imports_count_every_name():
    result = analyze("import os, sys\nfrom math import sqrt, pi\n")
    assert result["imports"] == 4


def test_nesting_depth():
    code = "if a:\n    for i in b:\n        while c:\n            pass\n"
    result = analyze(code)
    assert result["max_nesting_depth"] == 3
    assert result["cyclomatic_complexity"] == 4


def test_elif_chain_is_not_deep():
    code = "if a:\n    pass\nelif b:\n    pass\nelif c:\n    pass\nelse:\n    pass\n"
    result = analyze(code)
    assert result["max_nesting_depth"] == 1
    assert result["cyclomatic_complexity"] == 4


def test_else_body_counts_as_nested():
    code = "if a:\n    pass\nelse:\n    for i in b:\n        pass\n"
    result = analyze(code)
    assert result["max_nesting_depth"] == 2
    assert result["cyclomatic_complexity"] == 3


def test_except_and_boolean_operators():
    code = (
        "try:\n    x = 1\n"
        "except ValueError:\n    pass\n"
        "except TypeError:\n    pass\n"
        "if a and b or c:\n    pass\n"
    )
    result = analyze(code)
    # 2 excepts + 1 if + 2 boolean operators = 5 decision points
    assert result["cyclomatic_complexity"] == 6
    assert result["max_nesting_depth"] == 1
    assert result["variables"] == 1


def test_comprehension():
    code = "data = [1, 2]\nresult = [n for n in data if n > 0]\n"
    result = analyze(code)
    assert result["cyclomatic_complexity"] == 3  # loop + if
    assert result["variables"] == 3  # data, result, n


def test_ternary():
    result = analyze("y = 1 if a else 2\n")
    assert result["cyclomatic_complexity"] == 2


def test_analyze_twice_gives_same_answer():
    analyzer = PythonAnalyzer("for i in x:\n    pass\n")
    assert analyzer.analyze() == analyzer.analyze()


def test_broken_code_still_gets_line_counts():
    result = analyze("def broken(:\n    pass\n")
    assert result["ast_available"] is False
    assert result["total_lines"] == 2
    assert "functions" not in result


def test_empty_code():
    result = analyze("")
    assert result["total_lines"] == 0
    assert result["code_lines"] == 0
    assert result["ast_available"] is True
    assert result["cyclomatic_complexity"] == 1