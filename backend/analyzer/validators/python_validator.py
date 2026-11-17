import ast

from .base import BaseValidator


class PythonValidator(BaseValidator):
    """Checks that Python code is valid Python. It never runs the code.

    Two stages, so we can tell the user what kind of problem it is:
      1. syntax:  can Python read the code at all?   (ast.parse)
      2. compile: does Python accept the whole program?   (compile)
    """

    def validate(self, code: str, file_path: str = "<unknown>") -> dict:
        # Stage 1: syntax
        error = self._catch(
            "syntax", file_path, lambda: ast.parse(code, filename=file_path)
        )

        # Stage 2: compile. Only if stage 1 passed.
        # compile() builds bytecode but does NOT run it.
        if error is None:
            error = self._catch(
                "compile",
                file_path,
                lambda: compile(code, file_path, "exec", dont_inherit=True),
            )

        if error is None:
            return {"valid": True, "language": "Python", "errors": []}
        return {"valid": False, "language": "Python", "errors": [error]}

    def _catch(self, stage, file_path, action):
        """Run action(). Returns an error dict if it fails, otherwise None."""
        try:
            action()
            return None
        except SyntaxError as error:
            # IndentationError and TabError are kinds of SyntaxError.
            # type(error).__name__ keeps their real names.
            return self._error(
                stage, type(error).__name__, error.msg, file_path, error.lineno, error.offset
            )
        except ValueError as error:
            # Older Python versions raise this for null bytes in the code.
            return self._error(stage, "ValueError", str(error), file_path)
        except (RecursionError, MemoryError):
            return self._error(
                stage,
                "TooComplex",
                "The code is too deeply nested or too large to check.",
                file_path,
            )

    def _error(self, stage, error_type, message, file_path, line=None, column=None) -> dict:
        return {
            "type": error_type,
            "stage": stage,
            "severity": "error",
            "file": file_path,
            "line": line,
            "column": column,
            "message": message,
        }