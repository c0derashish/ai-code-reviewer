from analyzer.static.python_analyzer import PythonAnalyzer

code = """
def process(data):

    if data:

        for item in data:

            if item > 10:
                print(item)

    return data
"""

analyzer = PythonAnalyzer()

result = analyzer.analyze(code)

print(result)