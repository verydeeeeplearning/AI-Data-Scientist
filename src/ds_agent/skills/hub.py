"""SkillHub — skill discovery, loading, management, and search."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger()

_DEFAULT_FILESYSTEM_PERMISSIONS = ("workspace",)


@dataclass(frozen=True, slots=True)
class SkillPermissions:
    """Optional permission hints declared by a skill."""

    network: tuple[str, ...] = ()
    filesystem: tuple[str, ...] = _DEFAULT_FILESYSTEM_PERMISSIONS

    def to_dict(self) -> dict[str, list[str]]:
        """Return a JSON-friendly permissions payload."""
        return {
            "network": list(self.network),
            "filesystem": list(self.filesystem),
        }


@dataclass
class SkillEntry:
    """A loaded skill with metadata and content."""

    name: str
    description: str
    category: str
    tags: list[str]
    content: str
    token_estimate: int = 0
    version: str = "1.0.0"
    author: str = "builtin"
    related_skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    permissions: SkillPermissions = field(default_factory=SkillPermissions)
    enabled: bool = True
    source_kind: str = "builtin"
    source_path: Path | None = None


class SkillHub:
    """Skill discovery, loading, search, and lightweight custom-skill management."""

    def __init__(
        self,
        skills: dict[str, SkillEntry] | None = None,
        *,
        directories: list[Path] | None = None,
        custom_dir: Path | None = None,
    ) -> None:
        self._skills: dict[str, SkillEntry] = skills or {}
        self._directories = [Path(item) for item in directories or []]
        self._custom_dir = Path(custom_dir) if custom_dir is not None else None

    @classmethod
    def from_directories(cls, directories: list[Path]) -> SkillHub:
        """Load skills from one or more directories (recursive)."""
        normalized = [Path(directory) for directory in directories]
        hub = cls(
            skills={},
            directories=normalized,
            custom_dir=_resolve_custom_dir(normalized),
        )
        hub.refresh()
        return hub

    def refresh(self) -> None:
        """Reload all skills from configured directories."""
        from ds_agent.skills.parser import parse_skill_file

        skills: dict[str, SkillEntry] = {}
        for directory in self._directories:
            if not directory.exists():
                continue
            for md_file in sorted(directory.rglob("*.md")):
                entry = parse_skill_file(md_file)
                if entry is None:
                    continue
                skills[entry.name] = entry
                logger.debug("skill_loaded", name=entry.name, path=str(md_file))
        self._skills = skills

    def list_skills(self, category: str | None = None) -> list[dict]:
        """List skill summaries without full markdown content."""
        results = []
        for entry in self._skills.values():
            if category and entry.category != category:
                continue
            results.append(self._to_summary(entry))
        results.sort(key=lambda item: item["name"])
        return results

    def list_manageable_skills(self) -> list[dict]:
        """Return custom skills that can be edited in the UI."""
        return [
            self._to_summary(entry)
            for entry in sorted(self._skills.values(), key=lambda item: item.name)
            if entry.source_kind == "custom"
        ]

    def view_skill(self, name: str) -> dict | None:
        """View full skill content by name."""
        entry = self._skills.get(name)
        if entry is None:
            return None
        return {
            **self._to_summary(entry),
            "content": entry.content,
            "related_skills": entry.related_skills,
        }

    def search_skills(self, query: str, category: str | None = None) -> list[dict]:
        """Search skills by keyword in name, description, tags, and tools."""
        query_lower = query.lower().strip()
        results = []

        for entry in self._skills.values():
            if category and entry.category != category:
                continue

            if not query_lower:
                results.append(self._to_summary(entry))
                continue

            searchable = " ".join(
                [
                    entry.name,
                    entry.description,
                    " ".join(entry.tags),
                    " ".join(entry.tools),
                    " ".join(entry.permissions.network),
                ]
            ).lower()
            if query_lower in searchable:
                results.append(self._to_summary(entry))

        results.sort(key=lambda item: item["name"])
        return results

    def get_skill_names(self) -> list[str]:
        """Get all loaded skill names."""
        return list(self._skills.keys())

    def get_enabled_prompt_skill_names(self, base_skill_names: list[str]) -> list[str]:
        """Return base skills plus enabled custom skills."""
        names = list(dict.fromkeys(base_skill_names))
        for entry in sorted(self._skills.values(), key=lambda item: item.name):
            if entry.source_kind == "custom" and entry.enabled:
                names.append(entry.name)
        return list(dict.fromkeys(names))

    def get_effective_permissions_for_tool(self, tool_name: str) -> dict[str, list[str]]:
        """Return the merged permissions of enabled custom skills for one tool."""
        network: set[str] = set()
        filesystem: set[str] = set(_DEFAULT_FILESYSTEM_PERMISSIONS)
        for entry in self._skills.values():
            if entry.source_kind != "custom" or not entry.enabled:
                continue
            if entry.tools and tool_name not in entry.tools:
                continue
            network.update(entry.permissions.network)
            filesystem.update(entry.permissions.filesystem)
        return {
            "network": sorted(network),
            "filesystem": sorted(filesystem),
        }

    def save_custom_skill(
        self,
        *,
        name: str,
        description: str,
        content: str,
        category: str = "custom",
        tags: list[str] | None = None,
        tools: list[str] | None = None,
        permissions: dict[str, list[str]] | None = None,
        enabled: bool = True,
        existing_name: str | None = None,
        version: str = "1.0.0",
        author: str = "user",
    ) -> dict:
        """Create or update one custom skill file and reload the hub entry."""
        custom_dir = self._require_custom_dir()
        normalized_name = name.strip()
        normalized_description = description.strip()
        if not normalized_name:
            raise ValueError("Skill name is required")
        if not normalized_description:
            raise ValueError("Skill description is required")

        safe_tags = _normalize_string_list(tags or [])
        safe_tools = _normalize_string_list(tools or [])
        safe_permissions = {
            "network": _normalize_string_list((permissions or {}).get("network", [])),
            "filesystem": _normalize_string_list(
                (permissions or {}).get("filesystem", list(_DEFAULT_FILESYSTEM_PERMISSIONS))
            )
            or list(_DEFAULT_FILESYSTEM_PERMISSIONS),
        }
        markdown = _render_skill_markdown(
            name=normalized_name,
            description=normalized_description,
            category=category.strip() or "custom",
            tags=safe_tags,
            content=content.strip(),
            version=version,
            author=author,
            enabled=enabled,
            tools=safe_tools,
            permissions=safe_permissions,
        )

        target = custom_dir / f"{_slugify(normalized_name)}.md"
        target.write_text(markdown, encoding="utf-8")

        if existing_name and existing_name != normalized_name:
            previous = self._skills.get(existing_name)
            if previous is not None and previous.source_path is not None:
                previous.source_path.unlink(missing_ok=True)

        self.refresh()
        entry = self._skills.get(normalized_name)
        if entry is None:
            raise ValueError(f"Failed to save skill: {normalized_name}")
        return self.view_skill(entry.name) or {}

    def import_custom_skill(self, raw_markdown: str) -> dict:
        """Import one raw markdown skill into the custom skill directory."""
        from ds_agent.skills.parser import parse_skill_text

        custom_dir = self._require_custom_dir()
        parsed = parse_skill_text(raw_markdown, source_path=custom_dir / "import.md")
        if parsed is None:
            raise ValueError("Invalid skill markdown. Required frontmatter fields are missing.")
        target = custom_dir / f"{_slugify(parsed.name)}.md"
        target.write_text(raw_markdown.strip() + "\n", encoding="utf-8")
        self.refresh()
        return self.view_skill(parsed.name) or {}

    def delete_custom_skill(self, name: str) -> bool:
        """Delete one custom skill markdown file."""
        entry = self._skills.get(name)
        if entry is None or entry.source_kind != "custom" or entry.source_path is None:
            return False
        entry.source_path.unlink(missing_ok=True)
        self.refresh()
        return True

    def set_skill_enabled(self, name: str, enabled: bool) -> dict:
        """Persist the enabled flag for one custom skill."""
        entry = self._skills.get(name)
        if entry is None or entry.source_kind != "custom":
            raise ValueError(f"Custom skill not found: {name}")
        return self.save_custom_skill(
            name=entry.name,
            description=entry.description,
            content=entry.content,
            category=entry.category,
            tags=list(entry.tags),
            tools=list(entry.tools),
            permissions=entry.permissions.to_dict(),
            enabled=enabled,
            existing_name=entry.name,
            version=entry.version,
            author=entry.author,
        )

    @staticmethod
    def _to_summary(entry: SkillEntry) -> dict:
        return {
            "name": entry.name,
            "description": entry.description,
            "category": entry.category,
            "tags": entry.tags,
            "token_estimate": entry.token_estimate,
            "version": entry.version,
            "author": entry.author,
            "enabled": entry.enabled,
            "sourceKind": entry.source_kind,
            "sourcePath": str(entry.source_path) if entry.source_path is not None else None,
            "tools": list(entry.tools),
            "permissions": entry.permissions.to_dict(),
        }

    def _require_custom_dir(self) -> Path:
        if self._custom_dir is None:
            raise ValueError("Custom skill directory is not configured")
        self._custom_dir.mkdir(parents=True, exist_ok=True)
        return self._custom_dir


def _resolve_custom_dir(directories: list[Path]) -> Path | None:
    for directory in directories:
        if directory.name == "custom" or "custom" in directory.parts:
            return directory
    return None


def _normalize_string_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        item = value.strip()
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "custom-skill"


def _render_skill_markdown(
    *,
    name: str,
    description: str,
    category: str,
    tags: list[str],
    content: str,
    version: str,
    author: str,
    enabled: bool,
    tools: list[str],
    permissions: dict[str, list[str]],
) -> str:
    frontmatter: dict[str, object] = {
        "name": name,
        "description": description,
        "category": category,
        "tags": tags,
        "version": version,
        "author": author,
        "enabled": enabled,
    }
    if tools:
        frontmatter["tools"] = tools
    if permissions.get("network") or permissions.get("filesystem"):
        perm_block: dict[str, object] = {}
        if permissions.get("network"):
            perm_block["network"] = permissions["network"]
        if permissions.get("filesystem"):
            perm_block["filesystem"] = permissions["filesystem"]
        frontmatter["permissions"] = perm_block

    yaml_text = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    body = content.strip() or f"# {name}\n\nDescribe the workflow here."
    return f"---\n{yaml_text}\n---\n\n{body}\n"
