import ast


class PythonAnalyzer(ast.NodeVisitor):

    def __init__(self, code: str):

        self.code = code
        self.tree = ast.parse(code)

        self.functions = 0
        self.classes = 0
        self.imports = 0
        self.variables = 0

        self.max_nesting = 0
        self.current_nesting = 0

        self.total_branches = 0

    def analyze(self):

        self.visit(self.tree)

        lines = self.code.splitlines()

        total_lines = len(lines)

        blank_lines = sum(
            1 for line in lines
            if not line.strip()
        )

        comment_lines = sum(
            1 for line in lines
            if line.strip().startswith("#")
        )

        return {
            "lines_of_code": total_lines,
            "blank_lines": blank_lines,
            "comment_lines": comment_lines,
            "functions": self.functions,
            "classes": self.classes,
            "imports": self.imports,
            "variables": self.variables,
            "cyclomatic_complexity": 1 + self.total_branches,
            "max_nesting_depth": self.max_nesting
        }

    # -------------------------
    # Functions
    # -------------------------

    def visit_FunctionDef(self, node):

        self.functions += 1

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):

        self.functions += 1

        self.generic_visit(node)

    # -------------------------
    # Classes
    # -------------------------

    def visit_ClassDef(self, node):

        self.classes += 1

        self.generic_visit(node)

    # -------------------------
    # Imports
    # -------------------------

    def visit_Import(self, node):

        self.imports += 1

        self.generic_visit(node)

    def visit_ImportFrom(self, node):

        self.imports += 1

        self.generic_visit(node)

    # -------------------------
    # Variables
    # -------------------------

    def visit_Assign(self, node):

        self.variables += len(node.targets)

        self.generic_visit(node)

    # -------------------------
    # Complexity
    # -------------------------

    def visit_If(self, node):

        self.total_branches += 1

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()


    def visit_For(self, node):

        self.total_branches += 1

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()


    def visit_While(self, node):

        self.total_branches += 1

        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()


    def visit_IfExp(self, node):

        self.total_branches += 1

        self.generic_visit(node)

    # -------------------------
    # Nesting
    # -------------------------

    def _enter_nesting(self):

        self.current_nesting += 1

        self.max_nesting = max(
            self.max_nesting,
            self.current_nesting
        )

    def _exit_nesting(self):

        self.current_nesting -= 1