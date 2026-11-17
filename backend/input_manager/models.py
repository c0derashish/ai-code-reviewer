from dataclasses import dataclass, field
from typing import Optional


class InputError(Exception):
    """The input cannot be used. The message is safe to show to the user."""


@dataclass
class CodeFile:
    file_path: str   # path inside the project, always with "/" like "src/app.py"
    source_code: str
    size_bytes: int
    language: Optional[str] = None           # filled in Phase 2
    validation_result: Optional[dict] = None  # filled in Phase 3
    analysis_result: Optional[dict] = None    # filled in Phase 4


@dataclass
class SkippedFile:
    file_path: str
    reason: str


@dataclass
class CodeProject:
    project_id: str
    project_name: str
    input_type: str  # "single_file" or "project" (GitHub comes later)
    files: list = field(default_factory=list)
    skipped: list = field(default_factory=list)  # first few skipped files only
    skipped_count: int = 0                       # how many were skipped in total
    detected_languages: dict = field(default_factory=dict)  # Phase 2
    primary_language: Optional[str] = None                  # Phase 2

    @property
    def file_count(self) -> int:
        return len(self.files)

    def get_file(self, file_path: str) -> Optional[CodeFile]:
        for code_file in self.files:
            if code_file.file_path == file_path:
                return code_file
        return None