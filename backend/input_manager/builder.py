import uuid

from .models import CodeFile, CodeProject, InputError, SkippedFile
from .rules import (
    IGNORED_FOLDERS,
    MAX_FILES,
    MAX_SKIPPED_LISTED,
    MAX_TOTAL_BYTES,
    SOURCE_EXTENSIONS,
    clean_path,
    clean_project_name,
    get_extension,
    size_problem,
)


def read_text(data: bytes):
    """Turn file bytes into text. Returns (text, None) or (None, reason)."""
    if b"\x00" in data:
        return None, "binary file"
    try:
        # utf-8-sig removes the invisible BOM some editors put at the start
        return data.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return None, "not valid UTF-8 text"


class ProjectBuilder:
    """Collects files one by one. Every input source uses this class."""

    def __init__(self, project_name, input_type):
        self.project = CodeProject(
            project_id=uuid.uuid4().hex[:12],
            project_name=clean_project_name(project_name),
            input_type=input_type,
        )
        self.total_bytes = 0
        self.seen_paths = set()

    def skip(self, path, reason):
        self.project.skipped_count += 1
        # keep the list short, so a huge folder cannot create a huge answer
        if len(self.project.skipped) < MAX_SKIPPED_LISTED:
            self.project.skipped.append(SkippedFile(str(path)[:200], reason))

    def precheck(self, raw_path, size):
        """Checks that need no file content. Returns (path, None) or (None, reason)."""
        path, reason = clean_path(raw_path)
        if reason:
            return None, reason

        folders = path.split("/")[:-1]
        if any(folder.lower() in IGNORED_FOLDERS for folder in folders):
            return None, "inside an ignored folder"

        if get_extension(path) not in SOURCE_EXTENSIONS:
            return None, "unsupported file type"

        reason = size_problem(size)
        if reason:
            return None, reason

        if path in self.seen_paths:
            return None, "duplicate path"

        return path, None

    def add(self, raw_path, data: bytes):
        """Add a file whose bytes we already have."""
        self.add_lazy(raw_path, len(data), lambda: data)

    def add_lazy(self, raw_path, size, read_bytes):
        """Add a file but read its bytes only if the cheap checks pass.

        read_bytes is a function. Local folders use this so a huge or
        unsupported file is never loaded into memory.
        """
        path, reason = self.precheck(raw_path, size)
        if reason:
            self.skip(raw_path, reason)
            return

        try:
            data = read_bytes()
        except OSError:
            self.skip(path, "file could not be read")
            return

        self._accept(path, data)

    def _accept(self, path, data):
        # check again with the real size, the file may have changed
        reason = size_problem(len(data))
        if reason:
            self.skip(path, reason)
            return

        text, reason = read_text(data)
        if reason:
            self.skip(path, reason)
            return

        # these two stop the whole project, not just one file
        if self.project.file_count >= MAX_FILES:
            raise InputError(f"Too many files. The limit is {MAX_FILES}.")
        if self.total_bytes + len(data) > MAX_TOTAL_BYTES:
            raise InputError(
                f"Project is larger than {MAX_TOTAL_BYTES // (1024 * 1024)} MB in total."
            )

        self.seen_paths.add(path)
        self.total_bytes += len(data)
        self.project.files.append(
            CodeFile(file_path=path, source_code=text, size_bytes=len(data))
        )

    def finish(self) -> CodeProject:
        if self.project.file_count == 0:
            supported = " ".join(sorted(SOURCE_EXTENSIONS))
            raise InputError(f"No supported source files found. Supported types: {supported}")

        self.project.files.sort(key=lambda code_file: code_file.file_path)
        return self.project