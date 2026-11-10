"""
Raw Code Input Handler
Manages directly pasted code with language detection and metadata tracking.
Maintains consistent metadata structure with repo_clone and local_project_uploader.
"""

import hashlib
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RawCodeInputHandler:
    """
    Manages raw code input with automatic language detection.
    
    Architecture:
    - Code storage: D:\sem 7th project\ai-code-reviewer\clone_repo_local_path
    - Metadata path: D:\sem 7th project\ai-code-reviewer\clone_repo_metedata
    - Each snippet: clone_repo_local_path\raw_code\{snippet_id}.{ext}
    - Each metadata: clone_repo_metadata\{snippet_id}.json
    
    Supports:
    - Direct code pasting
    - Automatic language detection
    - Language hints from user
    - Metadata tracking and retrieval
    """

    # Language detection patterns
    LANGUAGE_PATTERNS = {
        "Python": {
            "extensions": [".py", ".pyw", ".pyi"],
            "keywords": [
                "def ", "class ", "import ", "from ", "if __name__",
                "async ", "await ", "with ", "for ", "while "
            ],
            "patterns": [
                r"^#!/usr/bin/env python",
                r"^# -*- coding:",
                r"^import\s+\w+",
                r"^from\s+\w+\s+import"
            ]
        },
        "JavaScript": {
            "extensions": [".js", ".jsx", ".mjs"],
            "keywords": [
                "function ", "const ", "let ", "var ", "import ",
                "export ", "async ", "await ", "class ", "=>",
                "console.log", "require("
            ],
            "patterns": [
                r"^#!/usr/bin/env node",
                r"^const\s+\w+\s*=",
                r"^function\s+\w+",
                r"^(import|export)\s+"
            ]
        },
        "Java": {
            "extensions": [".java"],
            "keywords": [
                "public class ", "private ", "protected ", "import ",
                "package ", "void ", "String ", "int ", "public static",
                "new "
            ],
            "patterns": [
                r"^package\s+[\w.]+;",
                r"^import\s+[\w.]+;",
                r"^public\s+class\s+\w+"
            ]
        },
        "TypeScript": {
            "extensions": [".ts", ".tsx"],
            "keywords": [
                "interface ", "type ", "enum ", ": string", ": number",
                "async ", "await ", "export ", "import ", "class ",
                "private ", "public "
            ],
            "patterns": [
                r":\s*(string|number|boolean|any|void)",
                r"^(interface|type|enum)\s+\w+",
                r"^import\s+.*from"
            ]
        },
        "C++": {
            "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
            "keywords": [
                "#include ", "using namespace ", "int main", "std::",
                "class ", "template ", "nullptr", "const ", "void ",
                "cout", "cin"
            ],
            "patterns": [
                r"^#include\s+[<\"]",
                r"^using\s+namespace\s+\w+;",
                r"^int\s+main\("
            ]
        },
        "C": {
            "extensions": [".c", ".h"],
            "keywords": [
                "#include ", "int main", "void ", "char ", "struct ",
                "malloc", "free", "printf", "scanf", "NULL"
            ],
            "patterns": [
                r"^#include\s+[<\"]",
                r"^int\s+main\(",
                r"malloc\s*\(",
                r"printf\s*\("
            ]
        },
        "Go": {
            "extensions": [".go"],
            "keywords": [
                "package ", "import ", "func ", "type ", "interface ",
                "struct ", "defer ", "go ", "channel", "goroutine"
            ],
            "patterns": [
                r"^package\s+\w+",
                r"^import\s*\(",
                r"^func\s+\w+\("
            ]
        },
        "Rust": {
            "extensions": [".rs"],
            "keywords": [
                "fn ", "let ", "mut ", "impl ", "trait ", "struct ",
                "enum ", "pub ", "use ", "mod ", "crate::", "async"
            ],
            "patterns": [
                r"^fn\s+\w+",
                r"^use\s+\w+",
                r"^struct\s+\w+",
                r":\s*\w+\s*="
            ]
        },
        "PHP": {
            "extensions": [".php"],
            "keywords": [
                "<?php", "<?", "function ", "class ", "public ",
                "private ", "echo ", "print ", "array(", "$",
                "namespace "
            ],
            "patterns": [
                r"^<\?php",
                r"function\s+\w+\s*\(",
                r"class\s+\w+",
                r"\$\w+\s*="
            ]
        }
    }

    def __init__(
        self,
        code_base_dir: str = r"D:\sem 7th project\ai-code-reviewer\clone_repo_local_path\raw_code",
        metadata_dir: str = r"D:\sem 7th project\ai-code-reviewer\clone_repo_metedata"
    ):
        """
        Initialize raw code input handler.
        
        Args:
            code_base_dir: Directory for storing raw code snippets
            metadata_dir: Directory for storing metadata JSON files
        """
        self.code_base_dir = Path(code_base_dir)
        self.metadata_dir = Path(metadata_dir)
        
        # Create directories if they don't exist
        self.code_base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Raw code handler initialized")

    @staticmethod
    def _validate_code_input(code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate raw code input.
        
        Checks:
        - Not empty
        - Reasonable length (< 1MB)
        - Not binary/gibberish
        
        Returns:
            Tuple of (is_valid: bool, error_message: str|None)
        """
        if not code or not code.strip():
            return False, "Code input is empty"
        
        # Check size (1MB limit)
        if len(code) > 1024 * 1024:
            return False, "Code exceeds 1MB limit"
        
        # Check if mostly gibberish (non-printable characters)
        try:
            # Try to decode as UTF-8
            code.encode("utf-8")
        except UnicodeEncodeError:
            return False, "Code contains invalid characters"
        
        # Check if at least some valid characters exist
        valid_chars = sum(1 for c in code if c.isprintable() or c.isspace())
        if valid_chars / len(code) < 0.5:
            return False, "Code appears to contain mostly non-printable characters"
        
        return True, None

    def _detect_language_from_content(
        self,
        code: str,
        hint: Optional[str] = None
    ) -> str:
        """
        Detect programming language from code content.
        
        Strategy:
        1. If user provides hint, validate it
        2. Check for shebang
        3. Score each language based on keywords/patterns
        4. Return highest scoring language
        
        Args:
            code: Source code content
            hint: (Optional) User-provided language hint
        
        Returns:
            Detected language name
        """
        
        # If hint provided, validate and return if valid
        if hint:
            hint_lower = hint.lower()
            for lang in self.LANGUAGE_PATTERNS.keys():
                if lang.lower() == hint_lower:
                    logger.info(f"Using user hint: {lang}")
                    return lang
        
        # Check shebang
        if code.startswith("#!"):
            shebang = code.split("\n")[0].lower()
            if "python" in shebang:
                return "Python"
            elif "node" in shebang or "javascript" in shebang:
                return "JavaScript"
            elif "bash" in shebang or "sh" in shebang:
                # Not supported yet, fall through to pattern matching
                pass
        
        # Score each language
        scores = {}
        
        for language, patterns in self.LANGUAGE_PATTERNS.items():
            score = 0
            
            # Check keywords
            for keyword in patterns["keywords"]:
                # Case-insensitive search
                if keyword.lower() in code.lower():
                    score += 5
            
            # Check regex patterns (more specific)
            for pattern in patterns["patterns"]:
                matches = len(re.findall(pattern, code, re.MULTILINE | re.IGNORECASE))
                score += matches * 10
            
            scores[language] = score
        
        # Return highest scoring language
        if scores:
            detected = max(scores, key=scores.get)
            confidence = scores[detected]
            
            if confidence > 0:
                logger.info(
                    f"Detected language: {detected} (confidence: {confidence})"
                )
                return detected
        
        # Fallback
        logger.warning("Could not detect language with confidence. Defaulting to Python.")
        return "Python"

    @staticmethod
    def _get_file_extension(language: str) -> str:
        """
        Get file extension for detected language.
        
        Returns:
            File extension (e.g., ".py", ".js")
        """
        extension_map = {
            "Python": ".py",
            "JavaScript": ".js",
            "Java": ".java",
            "TypeScript": ".ts",
            "C++": ".cpp",
            "C": ".c",
            "Go": ".go",
            "Rust": ".rs",
            "PHP": ".php"
        }
        
        return extension_map.get(language, ".txt")

    @staticmethod
    def _generate_snippet_id(language: str) -> str:
        """
        Generate unique snippet ID.
        
        Format: raw_code_{language}_{timestamp}_{hash}
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"raw_code_{language}_{timestamp}"

    @staticmethod
    def _calculate_code_hash(code: str) -> str:
        """
        Calculate SHA256 hash of code for deduplication.
        
        Returns:
            Hex hash string
        """
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _save_code_file(
        self,
        code: str,
        snippet_id: str,
        language: str
    ) -> Tuple[bool, Path, Optional[str]]:
        """
        Save raw code to file.
        
        Returns:
            Tuple of (success: bool, file_path: Path, error: str|None)
        """
        try:
            extension = self._get_file_extension(language)
            file_path = self.code_base_dir / f"{snippet_id}{extension}"
            
            # Write code to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code)
            
            logger.info(f"Code saved: {file_path}")
            return True, file_path, None
        
        except Exception as e:
            error_msg = f"Failed to save code file: {str(e)}"
            logger.error(error_msg)
            return False, Path(), error_msg

    def _save_metadata(
        self,
        snippet_id: str,
        language: str,
        code: str,
        file_path: Path,
        status: str,
        error_message: Optional[str] = None
    ) -> Path:
        """
        Save snippet metadata as JSON.
        
        Metadata structure (consistent with other input methods):
        {
            "snippet_id": "...",
            "source_type": "raw_code_input",
            "language": "Python",
            "file_path": "...",
            "saved_at": "ISO timestamp",
            "status": "success|failed",
            "error": null or error message,
            "code_hash": "SHA256 hash",
            "code_length": number of characters,
            "line_count": number of lines,
            "char_count": total characters
        }
        """
        code_hash = self._calculate_code_hash(code)
        lines = code.split("\n")
        
        metadata = {
            "snippet_id": snippet_id,
            "source_type": "raw_code_input",
            "language": language,
            "file_path": str(file_path) if file_path.exists() else None,
            "saved_at": datetime.now().isoformat(),
            "status": status,
            "error": error_message,
            "code_hash": code_hash,
            "code_length": len(code),
            "line_count": len(lines),
            "char_count": len(code)
        }
        
        # Save metadata JSON
        metadata_file = self.metadata_dir / f"{snippet_id}.json"
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.info(f"Metadata saved: {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
        
        return metadata_file

    def submit_raw_code(
        self,
        code: str,
        language_hint: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Submit and process raw code input.
        
        Args:
            code: Source code as string
            language_hint: (Optional) User-provided language hint
                          e.g., "Python", "JavaScript", "Java"
        
        Returns:
            Tuple of (success: bool, message: str, metadata: dict|None)
            
        Example:
            success, message, metadata = handler.submit_raw_code(
                code='''
                def greet(name):
                    print(f"Hello, {name}!")
                
                greet("Mk")
                ''',
                language_hint="Python"
            )
            
            if success:
                print(f"Snippet ID: {metadata['snippet_id']}")
                print(f"Language: {metadata['language']}")
                print(f"Code path: {metadata['file_path']}")
        """
        
        # Validate input
        is_valid, error = self._validate_code_input(code)
        if not is_valid:
            logger.error(error)
            return False, error, None
        
        # Detect language
        detected_language = self._detect_language_from_content(code, language_hint)
        
        # Generate snippet ID
        snippet_id = self._generate_snippet_id(detected_language)
        
        logger.info(f"Processing snippet: {snippet_id}")
        
        # Save code file
        success, file_path, error_msg = self._save_code_file(
            code,
            snippet_id,
            detected_language
        )
        
        if not success:
            self._save_metadata(
                snippet_id,
                detected_language,
                code,
                Path(),
                status="failed",
                error_message=error_msg
            )
            return False, error_msg, None
        
        # Save metadata
        metadata_file = self._save_metadata(
            snippet_id,
            detected_language,
            code,
            file_path,
            status="success"
        )
        
        success_msg = (
            f"Successfully processed raw code snippet ({detected_language}) "
            f"- {len(code)} characters, {len(code.split(chr(10)))} lines"
        )
        logger.info(success_msg)
        
        # Return metadata
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        return True, success_msg, metadata

    def get_snippet_metadata(self, snippet_id: str) -> Optional[Dict]:
        """
        Retrieve metadata for a specific code snippet.
        
        Args:
            snippet_id: Snippet ID
        
        Returns:
            Metadata dictionary or None if not found
        """
        metadata_file = self.metadata_dir / f"{snippet_id}.json"
        
        if not metadata_file.exists():
            logger.warning(f"Metadata not found: {snippet_id}")
            return None
        
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")
            return None

    def get_snippet_code(self, snippet_id: str) -> Optional[str]:
        """
        Retrieve code content for a specific snippet.
        
        Args:
            snippet_id: Snippet ID
        
        Returns:
            Code content or None if not found
        """
        # Get metadata to find file path
        metadata = self.get_snippet_metadata(snippet_id)
        if not metadata:
            return None
        
        file_path = Path(metadata["file_path"])
        
        if not file_path.exists():
            logger.warning(f"Code file not found: {file_path}")
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read code: {e}")
            return None

    def list_submitted_snippets(self) -> list[Dict]:
        """
        List all submitted code snippets.
        
        Returns:
            List of metadata dictionaries
        """
        snippets = []
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        snippet_meta = json.load(f)
                        # Only include raw code inputs
                        if snippet_meta.get("source_type") == "raw_code_input":
                            snippets.append(snippet_meta)
                except Exception as e:
                    logger.warning(f"Failed to read metadata: {e}")
        
        except Exception as e:
            logger.error(f"Failed to list snippets: {e}")
        
        return snippets


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize handler
    handler = RawCodeInputHandler()
    
    # Example 1: Python code
    python_code = """
def calculate_sum(numbers):
    '''Calculate sum of numbers.'''
    total = 0
    for num in numbers:
        total += num
    return total

result = calculate_sum([1, 2, 3, 4, 5])
print(f"Sum: {result}")
"""
    
    print("=" * 60)
    print("Submitting Python code...")
    print("=" * 60)
    
    success, message, metadata = handler.submit_raw_code(python_code)
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    
    if metadata:
        print(f"\nMetadata:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        
        print(f"\nSnippet Details:")
        print(f"  ID: {metadata['snippet_id']}")
        print(f"  Language: {metadata['language']}")
        print(f"  Lines: {metadata['line_count']}")
        print(f"  Characters: {metadata['char_count']}")
        print(f"  Hash: {metadata['code_hash'][:16]}...")
    
    # Example 2: JavaScript code (without hint - auto-detect)
    js_code = """
function fetchUserData(userId) {
    return fetch(`/api/users/${userId}`)
        .then(response => response.json())
        .catch(error => console.error('Error:', error));
}

async function getUserInfo(id) {
    const data = await fetchUserData(id);
    return data;
}
"""
    
    print("\n" + "=" * 60)
    print("Submitting JavaScript code (auto-detect)...")
    print("=" * 60)
    
    success, message, metadata = handler.submit_raw_code(js_code)
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    
    if metadata:
        print(f"\nDetected language: {metadata['language']}")
        print(f"Code hash: {metadata['code_hash'][:16]}...")
    
    # Example 3: List all submitted snippets
    print("\n" + "=" * 60)
    print("All submitted snippets:")
    print("=" * 60)
    
    all_snippets = handler.list_submitted_snippets()
    for snippet in all_snippets:
        print(
            f"  - {snippet['snippet_id']} ({snippet['language']}) "
            f"- {snippet['line_count']} lines"
        )