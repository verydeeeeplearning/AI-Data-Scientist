"""Shared path resolution helpers for semantic packs."""

from __future__ import annotations

import re
from pathlib import Path

from ds_agent.tools.path_utils import is_within_workspace

_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def resolve_semantic_pack_dir(
    *,
    pack_dir: str | None,
    skill_name: str | None,
    workspace_dir: str | Path | None = None,
    skill_root: str | Path | None = None,
) -> tuple[Path, str]:
    """Resolve a semantic pack path from either a workspace path or built-in skill."""

    if bool(pack_dir) == bool(skill_name):
        raise ValueError("exactly one of 'pack_dir' or 'skill_name' must be provided")

    if skill_name is not None:
        normalized_name = skill_name.strip().lower()
        if not _SKILL_NAME_RE.fullmatch(normalized_name):
            raise ValueError(f"invalid semantic pack skill name: {skill_name!r}")
        root = Path(skill_root) if skill_root is not None else default_semantic_pack_skill_root()
        resolved = (root / normalized_name).resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(f"semantic pack skill not found: {normalized_name}")
        return resolved, "skill"

    if pack_dir is None:
        raise ValueError("pack_dir is required")

    workspace_path = (
        Path(workspace_dir).expanduser().resolve() if workspace_dir is not None else None
    )
    candidate = Path(pack_dir).expanduser()
    if workspace_path is not None and not candidate.is_absolute():
        candidate = workspace_path / candidate
    resolved = candidate.resolve()
    if workspace_path is not None and not is_within_workspace(resolved, workspace_path):
        raise ValueError(
            f"semantic pack path must stay inside the workspace boundary ({workspace_path})"
        )
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"semantic pack directory not found: {resolved}")
    return resolved, "workspace"


def default_semantic_pack_skill_root() -> Path:
    """Return the built-in semantic skill-pack root."""

    return Path(__file__).resolve().parents[3] / "skills" / "domain"
