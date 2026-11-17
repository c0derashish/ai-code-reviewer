import importlib.metadata
import os
import subprocess
import sys
import tempfile

# Limits. They protect the server from a tool that hangs or answers with too much.
TOOL_TIMEOUT_SECONDS = 60
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
MAX_FINDINGS_PER_TOOL = 2000
MAX_DETAIL_LENGTH = 300


class ToolError(Exception):
    """A tool could not run, or its answer could not be read."""


def get_tool_version(package_name):
    """Installed version of a tool, or None if it is not installed."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def base_name(path):
    """File name only. Works for paths with / and with backslash."""
    return str(path).replace("\\", "/").split("/")[-1]


def python_command(module_name):
    """Start a tool with the same Python that runs the server."""
    return [sys.executable, "-m", module_name]


def write_temp_files(folder, code_files):
    """Write each file under a SAFE name (f0001.py, f0002.py, ...).

    We never use the user's path on disk. This avoids path tricks and Windows
    reserved names. Returns {safe_name: original_path}.
    """
    names = {}
    for number, code_file in enumerate(code_files, start=1):
        safe_name = f"f{number:04d}.py"
        path = os.path.join(folder, safe_name)
        # newline="" keeps line endings as they are, so line numbers stay the same
        with open(path, "w", encoding="utf-8", newline="") as target:
            target.write(code_file.source_code)
        names[safe_name] = code_file.file_path
    return names


def run_command(args, folder):
    """Run a tool. No shell. Returns (exit_code, stdout_bytes, stderr_bytes)."""
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"

    try:
        done = subprocess.run(
            args,
            cwd=folder,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=TOOL_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"timed out after {TOOL_TIMEOUT_SECONDS} seconds") from None
    except OSError:
        raise ToolError("could not start the tool") from None

    return done.returncode, done.stdout, done.stderr


def _report(status, version, note=None, detail=None, count=0, truncated=False):
    return {
        "status": status,  # "ok", "unavailable", "skipped" or "failed"
        "version": version,
        "note": note,
        "detail": detail,  # for developers only. Do not show to users
        "finding_count": count,
        "truncated": truncated,
    }


def run_tool(package, build_command, parse_output, code_files):
    """Run one tool on all given files in one go.

    build_command(file_names) -> list of arguments
    parse_output(exit_code, stdout, stderr, names) -> list of findings
        (each finding is a dict with a "file_path" key). It raises ToolError
        when the answer cannot be read.

    Returns (report, findings_by_file). Never raises: a broken tool must not
    break the review.
    """
    version = get_tool_version(package)
    if version is None:
        note = f"{package} is not installed. Install it with: pip install {package}"
        return _report("unavailable", None, note), {}

    if not code_files:
        return _report("skipped", version, "No Python files to check."), {}

    stderr_text = ""
    try:
        with tempfile.TemporaryDirectory(prefix="vedix_") as folder:
            names = write_temp_files(folder, code_files)
            args = build_command(sorted(names))
            exit_code, stdout, stderr = run_command(args, folder)
            stderr_text = stderr.decode("utf-8", errors="replace")[:MAX_DETAIL_LENGTH]

            if len(stdout) > MAX_OUTPUT_BYTES:
                raise ToolError("the answer was too large")
            findings = parse_output(exit_code, stdout, stderr, names)
    except ToolError as error:
        return _report("failed", version, f"{package} failed: {error}", stderr_text), {}
    except OSError:
        return _report("failed", version, f"{package} could not be run on this computer."), {}

    truncated = len(findings) > MAX_FINDINGS_PER_TOOL
    findings = findings[:MAX_FINDINGS_PER_TOOL]

    by_file = {}
    for finding in findings:
        by_file.setdefault(finding["file_path"], []).append(finding)

    return _report("ok", version, count=len(findings), truncated=truncated), by_file