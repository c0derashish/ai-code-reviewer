import ast

from analyzer.static.python.complexity import ComplexityVisitor


def split_lines(code: str) -> list:
    """Split code into lines the way Python numbers them.

    Only normal line endings (LF, CRLF, CR) end a line.
    A final line ending does not create an extra empty line.
    """
    text = code.replace("\r\n", "\n").replace("\r", "\n")
    if text == "":
        return []

    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()  # "a" + newline is one line, not two
    return lines


class PythonAnalyzer(ast.NodeVisitor):
    """Counts simple facts about a whole Python file.

    How every number is counted is written in research/methodology.md.
    Call this on code that already passed the validator. If the code is
    broken anyway, analyze() still counts lines and says ast_available=False.
    """

    def __init__(self, code: str):
        self.code = code
        self._reset()

    def _reset(self):
        # analyze() calls this first, so calling it twice gives the same answer.
        self.functions = 0
        self.classes = 0
        self.imports = 0
        self.variable_names = set()

    def analyze(self) -> dict:
        self._reset()
        metrics = self._line_metrics()

        try:
            tree = ast.parse(self.code)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            # Broken code: we can count lines, but not the structure.
            metrics["ast_available"] = False
            return metrics

        self.visit(tree)

        # complexity and nesting come from the shared ComplexityVisitor
        complexity = ComplexityVisitor().measure(tree.body)

        metrics["functions"] = self.functions
        metrics["classes"] = self.classes
        metrics["imports"] = self.imports
        metrics["variables"] = len(self.variable_names)
        metrics["cyclomatic_complexity"] = 1 + complexity["decision_points"]
        metrics["max_nesting_depth"] = complexity["max_nesting"]
        metrics["ast_available"] = True
        return metrics

    # ---------- line counting ----------

    def _line_metrics(self) -> dict:
        lines = split_lines(self.code)

        total = len(lines)
        blank = sum(1 for line in lines if not line.strip())
        comment = sum(1 for line in lines if line.strip().startswith("#"))
        code = total - blank - comment

        return {
            "total_lines": total,
            "blank_lines": blank,
            "comment_lines": comment,
            "code_lines": code,
            "lines_of_code": code,  # old name kept. Now means code lines only
        }

    # ---------- structure counting ----------

    def visit_FunctionDef(self, node):
        self.functions += 1
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef  # async functions count too

    def visit_ClassDef(self, node):
        self.classes += 1
        self.generic_visit(node)

    def visit_Import(self, node):
        # "import os, sys" has two names, so it counts as two imports
        self.imports += len(node.names)
        self.generic_visit(node)

    visit_ImportFrom = visit_Import

    def visit_Name(self, node):
        # A name that is being assigned (Store) is a variable.
        # A set means a name assigned many times is counted once.
        if isinstance(node.ctx, ast.Store):
            self.variable_names.add(node.id)
        self.generic_visit(node)