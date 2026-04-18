"""File operations tool — read, write, list, search."""

import json
from pathlib import Path

from ds_agent.tools.path_utils import get_active_workspace, is_within_workspace
from ds_agent.tools.registry import tool


def _check_path_in_workspace(file_path: str) -> str | None:
    """Return error JSON if path is outside the active workspace, else None.

    When no workspace is set (e.g. tests, CLI without config), all paths are
    allowed for backward compatibility.
    """
    workspace = get_active_workspace()
    if workspace is None:
        return None
    try:
        resolved = Path(file_path).resolve()
    except (ValueError, OSError):
        return json.dumps({"error": f"Invalid path: {file_path}"})
    if not is_within_workspace(resolved, workspace):
        return json.dumps({
            "error": (
                f"Access denied: '{file_path}' resolves to {resolved}, "
                f"which is outside the workspace boundary ({workspace}). "
                f"Use an absolute path inside the workspace instead."
            )
        })
    return None


def _resolve_in_workspace(path_str: str) -> Path:
    """Resolve a path string relative to the active workspace.

    Empty, ``.``, or relative paths are anchored to the workspace root so the
    agent does not have to care about the Python process CWD. Invalid paths
    (e.g. embedded null bytes) are returned unresolved so downstream
    validators can surface a proper error JSON instead of raising.
    """
    workspace = get_active_workspace()
    try:
        if workspace is None:
            return Path(path_str or ".").resolve()

        candidate = Path(path_str or "")
        if not candidate.is_absolute():
            candidate = workspace / candidate
        return candidate.resolve()
    except (ValueError, OSError):
        # Let the caller's _check_path_in_workspace emit the error JSON.
        return Path(path_str or ".")


@tool(
    name="read_file",
    description=(
        "Read the raw text contents of a file. Use for code files, configs, or logs. "
        "For structured data analysis (CSV/Parquet/Excel), use 'data_loader' instead "
        "which returns parsed summary with schema, stats, and head rows. "
        "For large files, use head_lines to limit output."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to read",
            },
            "head_lines": {
                "type": "integer",
                "description": "Only return first N lines. Omit to read all.",
            },
        },
        "required": ["file_path"],
    },
    prompt=(
        "Reads a text file and returns its contents.\n"
        "- Use head_lines to limit output for large files\n"
        "- Supports CSV, JSON, TXT, MD, PY, and other text formats"
    ),
)
def read_file(file_path: str, head_lines: int | None = None) -> str:
    path = _resolve_in_workspace(file_path)
    err = _check_path_in_workspace(str(path))
    if err:
        return err
    if not path.exists():
        return json.dumps({"error": f"File not found: {path}"})
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if head_lines:
            all_lines = text.splitlines()
            lines = all_lines[:head_lines]
            text = "\n".join(lines)
            if len(lines) < len(all_lines):
                text += f"\n... ({len(all_lines)} total lines)"
        return text
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool(
    name="write_file",
    description="Write content to a file. Creates parent directories if needed.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    },
    safety_level="caution",
    prompt=(
        "Writes content to a file. Creates parent directories if needed.\n"
        "- Verify the path is within the workspace before writing\n"
        "- Prefer dedicated tools (generate_report, etc.) over raw writes"
    ),
)
def write_file(file_path: str, content: str) -> str:
    path = _resolve_in_workspace(file_path)
    err = _check_path_in_workspace(str(path))
    if err:
        return err
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return json.dumps({"success": True, "path": str(path), "bytes": len(content)})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool(
    name="list_files",
    description="List files in a directory, optionally filtered by pattern.",
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path to list",
            },
            "pattern": {
                "type": "string",
                "default": "*",
                "description": "Glob pattern to filter files (e.g., '*.csv', '**/*.py')",
            },
        },
        "required": ["directory"],
    },
    prompt="Lists files in a directory. Use pattern='*.csv' to filter by extension.",
)
def list_files(directory: str, pattern: str = "*") -> str:
    path = _resolve_in_workspace(directory)
    err = _check_path_in_workspace(str(path))
    if err:
        return err
    if not path.exists():
        return json.dumps({"error": f"Directory not found: {path}"})
    try:
        files = sorted(str(f) for f in path.glob(pattern) if f.is_file())
        return json.dumps({"files": files, "count": len(files), "directory": str(path)})
    except Exception as e:
        return json.dumps({"error": str(e)})
