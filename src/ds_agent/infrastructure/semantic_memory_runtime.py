"""Runtime helpers for resolving the active semantic-memory container."""

from __future__ import annotations

from pathlib import Path

from ds_agent.infrastructure.semantic_memory_container import (
    SemanticMemoryContainer,
    build_semantic_memory_container,
)
from ds_agent.infrastructure.semantic_memory_paths import (
    resolve_semantic_db_path as resolve_shared_semantic_db_path,
)
from ds_agent.tools.path_utils import get_active_workspace

_semantic_container: SemanticMemoryContainer | None = None


def set_semantic_memory_container(container: SemanticMemoryContainer | None) -> None:
    """Set or clear the process-wide semantic-memory container."""

    global _semantic_container
    _semantic_container = container


def get_semantic_memory_container() -> SemanticMemoryContainer:
    """Return the active semantic-memory container, building one when needed."""

    global _semantic_container
    if _semantic_container is not None:
        return _semantic_container

    workspace = get_active_workspace()
    workspace_dir = str(workspace) if workspace is not None else None
    db_path = resolve_semantic_db_path(workspace)
    _semantic_container = build_semantic_memory_container(
        workspace_dir=workspace_dir,
        db_path=str(db_path),
    )
    return _semantic_container


def resolve_semantic_db_path(workspace_dir: str | Path | None = None) -> Path:
    """Return the shared semantic-memory database path for a workspace."""

    if workspace_dir is None:
        workspace_dir = get_active_workspace()
    return resolve_shared_semantic_db_path(workspace_dir)
