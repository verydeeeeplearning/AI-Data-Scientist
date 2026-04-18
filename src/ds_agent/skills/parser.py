"""Skill markdown parser — YAML frontmatter + content extraction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import yaml

if TYPE_CHECKING:
    from ds_agent.skills.hub import SkillEntry

logger = structlog.get_logger()

REQUIRED_FIELDS = {"name", "description", "category", "tags"}


def parse_skill_file(file_path: Path) -> SkillEntry | None:
    """Parse a skill markdown file with YAML frontmatter."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("skill_read_error", path=str(file_path), error=str(e))
        return None
    return parse_skill_text(text, source_path=file_path)


def parse_skill_text(text: str, source_path: Path | None = None) -> SkillEntry | None:
    """Parse skill markdown text into a SkillEntry."""
    from ds_agent.skills.hub import SkillEntry, SkillPermissions

    if not text.startswith("---"):
        logger.debug("skill_no_frontmatter", path=str(source_path) if source_path else None)
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        logger.warning("skill_yaml_error", path=str(source_path) if source_path else None, error=str(e))
        return None

    if not isinstance(meta, dict):
        return None

    missing = REQUIRED_FIELDS - set(meta.keys())
    if missing:
        logger.debug(
            "skill_missing_fields",
            path=str(source_path) if source_path else None,
            missing=missing,
        )
        return None

    content = parts[2].strip()
    token_estimate = meta.get("token_estimate") or max(1, len(content) // 4)
    permissions_meta = meta.get("permissions", {})
    permission_network = []
    permission_filesystem = ["workspace"]
    if isinstance(permissions_meta, dict):
        permission_network = _normalize_str_list(permissions_meta.get("network", []))
        permission_filesystem = _normalize_str_list(permissions_meta.get("filesystem", ["workspace"]))
        if not permission_filesystem:
            permission_filesystem = ["workspace"]

    return SkillEntry(
        name=str(meta["name"]),
        description=str(meta["description"]),
        category=str(meta["category"]),
        tags=_normalize_str_list(meta.get("tags", [])),
        content=content,
        token_estimate=int(token_estimate),
        version=str(meta.get("version", "1.0.0")),
        author=str(meta.get("author", "builtin")),
        related_skills=_normalize_str_list(meta.get("related_skills", [])),
        tools=_normalize_str_list(meta.get("tools", [])),
        permissions=SkillPermissions(
            network=tuple(permission_network),
            filesystem=tuple(permission_filesystem),
        ),
        enabled=bool(meta.get("enabled", True)),
        source_kind=_infer_source_kind(source_path),
        source_path=source_path,
    )


def _normalize_str_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _infer_source_kind(source_path: Path | None) -> str:
    if source_path is None:
        return "unknown"
    parts = {part.lower() for part in source_path.parts}
    if "custom" in parts:
        return "custom"
    if "builtin" in parts:
        return "builtin"
    if "shared" in parts:
        return "shared"
    if "domain" in parts:
        return "domain"
    return "unknown"
