import os

from .builder import ProjectBuilder
from .models import CodeProject, InputError
from .rules import IGNORED_FOLDERS, MAX_SCANNED_ENTRIES, size_problem


def from_single_file(file_name, data: bytes) -> CodeProject:
    """One file whose bytes we have. Folder parts of the name are dropped."""
    name = str(file_name).replace("\\", "/").split("/")[-1]

    builder = ProjectBuilder(name, "single_file")
    builder.add(name, data)

    if builder.project.file_count == 0:
        # say exactly why this one file was not accepted
        raise InputError(f"{name}: {builder.project.skipped[0].reason}")
    return builder.finish()


def from_uploads(project_name, items) -> CodeProject:
    """Files sent by the browser. items = list of (path, bytes).

    The API will call this. Paths are kept as sent (only cleaned),
    because VEDIX matches issues to files by path.
    """
    input_type = "single_file" if len(items) == 1 else "project"
    builder = ProjectBuilder(project_name, input_type)

    for path, data in items:
        builder.add(path, data)
    return builder.finish()


def from_local_file(file_path) -> CodeProject:
    """One file from this computer's disk."""
    name = os.path.basename(str(file_path))

    if os.path.islink(file_path) or not os.path.isfile(file_path):
        raise InputError(f"{name}: file not found")

    try:
        reason = size_problem(os.path.getsize(file_path))
        if reason:
            raise InputError(f"{name}: {reason}")
        with open(file_path, "rb") as source:
            data = source.read()
    except OSError:
        raise InputError(f"{name}: file could not be read") from None

    return from_single_file(name, data)


def _is_inside(root, path) -> bool:
    """True if path really lives inside root (after resolving links)."""
    real = os.path.realpath(path)
    try:
        return os.path.commonpath([root, real]) == root
    except ValueError:  # for example, a different drive on Windows
        return False


def from_local_folder(folder) -> CodeProject:
    """A whole folder on this computer. Never runs anything inside it."""
    root = os.path.realpath(str(folder))
    if not os.path.isdir(root):
        raise InputError("Folder not found.")

    builder = ProjectBuilder(os.path.basename(root), "project")
    scanned = 0

    # os.walk does not follow symbolic links to folders by default
    for current, folders, names in os.walk(root):
        # edit the list in place so os.walk never enters these folders
        folders[:] = [
            name for name in sorted(folders)
            if name.lower() not in IGNORED_FOLDERS
            and not os.path.islink(os.path.join(current, name))
        ]

        for name in sorted(names):
            scanned += 1
            if scanned > MAX_SCANNED_ENTRIES:
                raise InputError("This folder has too many files to scan.")

            full_path = os.path.join(current, name)
            relative = os.path.relpath(full_path, root)

            if os.path.islink(full_path):
                builder.skip(relative, "symbolic link")
                continue
            if not _is_inside(root, full_path):
                builder.skip(relative, "outside the project folder")
                continue

            try:
                size = os.path.getsize(full_path)
            except OSError:
                builder.skip(relative, "file could not be read")
                continue

            builder.add_lazy(relative, size, lambda p=full_path: _read_file(p))

    return builder.finish()


def _read_file(full_path) -> bytes:
    with open(full_path, "rb") as source:
        return source.read()