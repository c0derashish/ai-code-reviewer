# Starting values for the rules. They are OUR choices. They are NOT standards.
# A smell appears when a value is strictly GREATER than its threshold.
# The values can be changed without touching the rules.
DEFAULT_THRESHOLDS = {
    "long_method_lines": 50,      # lines from "def" to the end of the function
    "max_parameters": 5,          # self/cls not counted
    "max_nesting_depth": 4,       # levels of if/for/while/try/with
    "max_complexity": 10,         # cyclomatic complexity of one function
    "large_class_lines": 300,     # lines of a class
    "large_class_methods": 20,    # methods in a class
}

SMELL_NAMES = {
    "long_method": "Long method",
    "too_many_parameters": "Too many parameters",
    "deep_nesting": "Deep nesting",
    "high_complexity": "High complexity",
    "large_class": "Large class",
}


def get_thresholds(custom=None) -> dict:
    """Default thresholds, with any custom values on top. A typo raises an error."""
    limits = dict(DEFAULT_THRESHOLDS)
    if custom:
        unknown = set(custom) - set(DEFAULT_THRESHOLDS)
        if unknown:
            raise ValueError("Unknown threshold name(s): " + ", ".join(sorted(unknown)))
        limits.update(custom)
    return limits


def _add_if_over(smells, rule, kind, target, line, value, limit, what):
    if value > limit:
        smells.append(
            {
                "rule": rule,
                "name": SMELL_NAMES[rule],
                "kind": kind,
                "target": target,
                "line": line,
                "value": value,
                "threshold": limit,
                "message": f"'{target}' {what}. The limit we use is {limit}.",
            }
        )


def find_smells(functions, classes, thresholds=None) -> list:
    """Checks every function and class against the thresholds."""
    limits = get_thresholds(thresholds)
    smells = []

    for function in functions:
        target = function["qualified_name"]
        line = function["start_line"]

        length = function["length"]
        _add_if_over(
            smells, "long_method", "function", target, line,
            length, limits["long_method_lines"], f"is {length} lines long",
        )

        parameters = function["parameters"]
        _add_if_over(
            smells, "too_many_parameters", "function", target, line,
            parameters, limits["max_parameters"], f"takes {parameters} parameters",
        )

        depth = function["max_nesting_depth"]
        _add_if_over(
            smells, "deep_nesting", "function", target, line,
            depth, limits["max_nesting_depth"], f"has code nested {depth} levels deep",
        )

        complexity = function["cyclomatic_complexity"]
        _add_if_over(
            smells, "high_complexity", "function", target, line,
            complexity, limits["max_complexity"], f"has cyclomatic complexity {complexity}",
        )

    for one_class in classes:
        target = one_class["qualified_name"]
        line = one_class["start_line"]
        length = one_class["length"]
        methods = one_class["methods"]

        # one finding per class: lines first, then methods
        if length > limits["large_class_lines"]:
            _add_if_over(
                smells, "large_class", "class", target, line,
                length, limits["large_class_lines"], f"is {length} lines long",
            )
        elif methods > limits["large_class_methods"]:
            _add_if_over(
                smells, "large_class", "class", target, line,
                methods, limits["large_class_methods"], f"has {methods} methods",
            )

    return smells