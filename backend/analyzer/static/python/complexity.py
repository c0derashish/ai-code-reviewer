import ast


class ComplexityVisitor(ast.NodeVisitor):
    """Counts decision points, nesting depth, returns and ternary expressions.

    skip_inner_definitions=False: measure everything below (used for a whole file).
    skip_inner_definitions=True:  do not enter functions or classes found inside.
                                  Used for one function, so an inner function is
                                  measured on its own and not added to its parent.

    The rules are written in research/methodology.md.
    """

    def __init__(self, skip_inner_definitions=False):
        self.skip_inner_definitions = skip_inner_definitions
        self._reset()

    def _reset(self):
        self.decision_points = 0
        self.conditional_expressions = 0
        self.returns = 0
        self.max_nesting = 0
        self.current_nesting = 0

    def measure(self, statements) -> dict:
        """statements is a list of AST nodes, for example tree.body or function.body."""
        self._reset()
        for statement in statements:
            self.visit(statement)

        return {
            "decision_points": self.decision_points,
            "conditional_expressions": self.conditional_expressions,
            "returns": self.returns,
            "max_nesting": self.max_nesting,
        }

    # ---------- inner functions and classes ----------

    def visit_FunctionDef(self, node):
        if not self.skip_inner_definitions:
            self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    # ---------- decision points ----------

    def visit_IfExp(self, node):
        self.decision_points += 1
        self.conditional_expressions += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.decision_points += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # "a and b and c" has 3 values and adds 2 decision points
        self.decision_points += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        # one for the loop, one for each "if" inside it
        self.decision_points += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Return(self, node):
        self.returns += 1
        self.generic_visit(node)

    # ---------- nesting depth ----------

    def _enter_nesting(self):
        self.current_nesting += 1
        self.max_nesting = max(self.max_nesting, self.current_nesting)

    def _exit_nesting(self):
        self.current_nesting -= 1

    def _visit_nested(self, node):
        self._enter_nesting()
        self.generic_visit(node)
        self._exit_nesting()

    def visit_For(self, node):
        self.decision_points += 1
        self._visit_nested(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node):
        self.decision_points += 1
        self._visit_nested(node)

    def visit_Try(self, node):
        self._visit_nested(node)

    visit_TryStar = visit_Try

    def visit_With(self, node):
        self._visit_nested(node)

    visit_AsyncWith = visit_With

    def visit_If(self, node):
        self.decision_points += 1
        self._enter_nesting()
        self.visit(node.test)
        for statement in node.body:
            self.visit(statement)

        # "elif" is stored as an If inside orelse. It is not deeper than
        # the first "if", so we leave the nesting before visiting it.
        # Limit: "else:" followed by one "if" is treated the same way.
        is_elif = len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
        if is_elif:
            self._exit_nesting()
            self.visit(node.orelse[0])
        else:
            for statement in node.orelse:
                self.visit(statement)
            self._exit_nesting()