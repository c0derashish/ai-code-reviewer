import ast

from analyzer.static.python.complexity import ComplexityVisitor


def has_docstring(node) -> bool:
    """True if the module, class or function has a non-empty docstring."""
    doc = ast.get_docstring(node)
    return doc is not None and doc.strip() != ""


def count_parameters(node, is_method) -> int:
    """All parameters, including *args and **kwargs.

    In a method, a first parameter called "self" or "cls" is not counted.
    """
    args = node.args
    names = [arg.arg for arg in args.posonlyargs + args.args]
    if is_method and names and names[0] in ("self", "cls"):
        names = names[1:]

    count = len(names) + len(args.kwonlyargs)
    if args.vararg:
        count += 1
    if args.kwarg:
        count += 1
    return count


class _Collector(ast.NodeVisitor):
    """Walks the tree once and collects every function and class."""

    def __init__(self):
        self.functions = []
        self.classes = []
        self.scope = []  # list of (kind, name), for example [("class", "Calculator")]

    def _qualified_name(self, name) -> str:
        return ".".join([scope_name for _, scope_name in self.scope] + [name])

    def visit_ClassDef(self, node):
        methods = sum(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) for item in node.body
        )
        self.classes.append(
            {
                "name": node.name,
                "qualified_name": self._qualified_name(node.name),
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "length": node.end_lineno - node.lineno + 1,
                "methods": methods,
                "has_docstring": has_docstring(node),
            }
        )

        self.scope.append(("class", node.name))
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        is_method = bool(self.scope) and self.scope[-1][0] == "class"
        # skip_inner_definitions: an inner function is measured on its own
        measured = ComplexityVisitor(skip_inner_definitions=True).measure(node.body)

        self.functions.append(
            {
                "name": node.name,
                "qualified_name": self._qualified_name(node.name),
                "start_line": node.lineno,  # the "def" line, decorators excluded
                "end_line": node.end_lineno,
                "length": node.end_lineno - node.lineno + 1,
                "parameters": count_parameters(node, is_method),
                "cyclomatic_complexity": 1 + measured["decision_points"],
                "max_nesting_depth": measured["max_nesting"],
                "returns": measured["returns"],
                "conditional_expressions": measured["conditional_expressions"],
                "has_docstring": has_docstring(node),
                "is_method": is_method,
            }
        )

        self.scope.append(("function", node.name))
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def collect_structure(tree):
    """Returns (functions, classes) for a parsed file, in source order."""
    collector = _Collector()
    collector.visit(tree)
    return collector.functions, collector.classes


def summarize_functions(functions) -> dict:
    if not functions:
        return {
            "function_count": 0,
            "average_length": None,
            "max_length": None,
            "average_complexity": None,
            "max_complexity": None,
            "max_nesting_depth": None,
        }

    count = len(functions)
    lengths = [function["length"] for function in functions]
    complexities = [function["cyclomatic_complexity"] for function in functions]

    return {
        "function_count": count,
        "average_length": round(sum(lengths) / count, 1),
        "max_length": max(lengths),
        "average_complexity": round(sum(complexities) / count, 1),
        "max_complexity": max(complexities),
        "max_nesting_depth": max(function["max_nesting_depth"] for function in functions),
    }