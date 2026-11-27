import io
import stat
import zipfile
import zlib

from input_manager.builder import ProjectBuilder
from input_manager.models import InputError
from input_manager.rules import MAX_FILE_BYTES, MAX_SCANNED_ENTRIES, MAX_TOTAL_BYTES
from repo_fetcher.github import FetchError

# Source files that would be read may add up to this much (declared sizes, before unpacking).
MAX_CANDIDATE_BYTES = 2 * MAX_TOTAL_BYTES


def _inner_path(info):
    """The path inside the repository. GitHub puts everything in one top folder, which is removed.
    Returns None for paths we cannot use."""
    name = info.filename.replace("\\", "/")
    if name.startswith("/"):
        return None
    parts = name.split("/", 1)
    if len(parts) < 2 or not parts[1]:
        return None
    return parts[1]

def _root_folder(entries) -> str:
    """The top folder name GitHub used inside the archive (it may show the branch or the commit)."""
    for info in entries:
        name = info.filename.replace("\\", "/")
        if "/" in name and not name.startswith("/"):
            return name.split("/", 1)[0][:100]
    return ""


def _read_member(archive, info):
    """The bytes of one file, at most MAX_FILE_BYTES + 1 of them."""
    try:
        with archive.open(info) as member:
            return member.read(MAX_FILE_BYTES + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError):
        # add_lazy treats OSError as "file could not be read" and skips the file
        raise OSError("member could not be read") from None


def project_from_zip(data, project_name):
    """Turn a repository ZIP into a CodeProject. Nothing is written to disk. Raises FetchError."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, NotImplementedError, zlib.error, EOFError):
        raise FetchError("The downloaded archive could not be read.") from None

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_SCANNED_ENTRIES:
            raise FetchError(
                f"The repository has too many files ({MAX_SCANNED_ENTRIES} is the limit)."
            )

        builder = ProjectBuilder(project_name, "project")

        # Pass 1: how much source would we read? Stops a small ZIP that unpacks to a huge size.
        candidate_bytes = 0
        for info in entries:
            inner = _inner_path(info)
            if info.is_dir() or inner is None:
                continue
            _, reason = builder.precheck(inner, info.file_size)
            if reason is None:
                candidate_bytes += info.file_size
        if candidate_bytes > MAX_CANDIDATE_BYTES:
            raise FetchError("The repository's source files are too large to analyse.")

        # Pass 2: add the files. The builder skips what it cannot use and says why.
        try:
            for info in entries:
                if info.is_dir():
                    continue
                inner = _inner_path(info)
                if inner is None:
                    builder.skip(info.filename, "unusable path")
                elif stat.S_ISLNK(info.external_attr >> 16):
                    builder.skip(inner, "symbolic link")
                elif info.flag_bits & 0x1:
                    builder.skip(inner, "encrypted file")
                else:
                    builder.add_lazy(
                        inner, info.file_size, lambda info=info: _read_member(archive, info)
                    )
            project = builder.finish()
            project.source_ref = _root_folder(entries)
            return project
        except InputError as error:
            raise FetchError(str(error)) from None