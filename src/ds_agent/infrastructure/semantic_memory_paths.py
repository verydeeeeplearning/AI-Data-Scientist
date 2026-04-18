"""Shared path resolution for semantic-memory SQLite files."""

from __future__ import annotations

from pathlib import Path

from ds_agent.runtime.transcript_store import get_runtime_storage_root


def resolve_semantic_db_path(workspace_dir: str | Path | None = None) -> Path:
    """Return the canonical semantic DB path with legacy fallback."""

    workspace_path = _coerce_workspace_path(workspace_dir)
    canonical = _canonical_semantic_db_path(workspace_path)
    if canonical.exists():
        return canonical

    for legacy_path in _legacy_semantic_db_paths(workspace_path):
        if legacy_path.exists():
            return legacy_path
    return canonical


def _canonical_semantic_db_path(workspace_path: Path) -> Path:
    runtime_root = get_runtime_storage_root(str(workspace_path))
    return runtime_root / "semantic" / "semantic_memory.db"


def _legacy_semantic_db_paths(workspace_path: Path) -> list[Path]:
    return [
        workspace_path / "semantic" / "semantic_memory.db",
        workspace_path / "data" / "memory" / "semantic" / "semantic_memory.db",
    ]


def _coerce_workspace_path(workspace_dir: str | Path | None) -> Path:
    if workspace_dir is None:
        return Path.cwd().resolve()
    if isinstance(workspace_dir, Path):
        return workspace_dir.expanduser().resolve()
    return Path(workspace_dir).expanduser().resolve()
