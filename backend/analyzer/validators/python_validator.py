import ast
from analyzer.validators.base import BaseValidator

class PythonValidator(BaseValidator):

    def validate(self, code: str) -> dict:

        try:
            ast.parse(code)

            return {
                "valid": True,
                "language": "Python",
                "errors": []
            }

        except SyntaxError as error:

            return {
                "valid": False,
                "language": "Python",
                "errors": [
                    {
                        "type": "SyntaxError",
                        "line": error.lineno,
                        "column": error.offset,
                        "message": error.msg
                    }
                ]
            }