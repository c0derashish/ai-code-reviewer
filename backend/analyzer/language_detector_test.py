from analyzer.language_detector import detect_repository_languages


result = detect_repository_languages(
    "language_detector.py"
)

print(result)