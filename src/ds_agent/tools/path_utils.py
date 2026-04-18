"""Path validation utilities — shared workspace boundary checks."""

from __future__ import annotations

from pathlib import Path

# Active workspace set at agent-creation time; None means no boundary enforced.
_workspace_dir: Path | None = None


def set_active_workspace(path: Path | None) -> None:
    """Set the active workspace for runtime boundary checks.

    Called by create_agent() at startup. Affects all file operations and
    sandboxed DS tool executions.
    """
    global _workspace_dir
    _workspace_dir = path.resolve() if path else None


def get_active_workspace() -> Path | None:
    """Return the currently active workspace directory, or None if not set."""
    return _workspace_dir


def is_within_workspace(target: Path, workspace: Path) -> bool:
    """Check that target path is strictly within workspace directory.

    Uses Path.is_relative_to() instead of str.startswith() to prevent
    sibling-directory bypass (e.g. /workspace2 matching /workspace).
    """
    try:
        return target.resolve().is_relative_to(workspace.resolve())
    except (ValueError, OSError):
        return False
