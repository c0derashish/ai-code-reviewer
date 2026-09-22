from analyzer.validators.python_validator import PythonValidator


code = """
def add(a, b)
    return a + b
"""


validator = PythonValidator()

result = validator.validate(code)

print(result)