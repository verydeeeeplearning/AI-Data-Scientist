"""Template registry helpers for delivery rendering."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ds_agent.domain.entities.delivery_pack import ArtifactFormat, DeliveryTemplate


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    """Simple in-memory template definition used by tests and wrappers."""

    template_ref: str
    source_path: Path | None = None
    skeleton_sections: tuple[str, ...] = ()
    title: str | None = None

    def skeleton_for(self, structure: Sequence[str]) -> str:
        sections = tuple(structure) or self.skeleton_sections
        if not sections:
            return ""
        lines = ["Use exactly these sections in order:"]
        lines.extend(f"- {section}" for section in sections)
        return "\n".join(lines)


class TemplateRegistry:
    """Small in-memory registry used by phase-1 tests and wrappers."""

    def __init__(self, templates: Mapping[str, TemplateDefinition]) -> None:
        self._templates = dict(templates)

    def load(self, template_ref: str) -> TemplateDefinition:
        try:
            return self._templates[template_ref]
        except KeyError as exc:
            raise KeyError(f"Unknown template_ref: {template_ref}") from exc


class StaticTemplateRegistry:
    """Load delivery templates from a checked-in JSON registry."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self._registry_path = registry_path or self._default_registry_path()

    def load(
        self,
        template_ref: str,
        *,
        format: ArtifactFormat,
        fallback_structure: Sequence[str],
    ) -> DeliveryTemplate:
        payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
        raw_template = payload.get("templates", {}).get(template_ref)
        if raw_template is None:
            return DeliveryTemplate(
                template_ref=template_ref,
                family=template_ref.split("/")[1] if "/" in template_ref else template_ref,
                format=format,
                title=template_ref.split("/")[-2].replace("_", " ").title()
                if "/" in template_ref
                else template_ref,
                default_structure=tuple(fallback_structure),
            )
        template_path = raw_template.get("template_path")
        resolved_path: str | None = None
        if isinstance(template_path, str):
            candidate = (self._registry_path.parent / template_path).resolve()
            resolved_path = str(candidate)
        return DeliveryTemplate(
            template_ref=template_ref,
            family=str(raw_template["family"]),
            format=ArtifactFormat(str(raw_template["format"])),
            title=str(raw_template["title"]),
            default_structure=tuple(
                str(item) for item in raw_template.get("default_structure", [])
            ),
            template_path=resolved_path,
        )

    @staticmethod
    def _default_registry_path() -> Path:
        return Path(__file__).resolve().parents[4] / "assets" / "templates" / "registry.json"


def coerce_template(
    registry: object,
    *,
    template_ref: str,
    format: ArtifactFormat,
    fallback_structure: Sequence[str],
    fallback_title: str,
) -> DeliveryTemplate:
    """Resolve any supported registry/template object into a DeliveryTemplate."""

    if isinstance(registry, DeliveryTemplate):
        return registry
    if hasattr(registry, "template_ref") and hasattr(registry, "format"):
        path = getattr(registry, "path", None) or getattr(registry, "template_path", None)
        structure_value = getattr(registry, "structure", None) or getattr(
            registry,
            "default_structure",
            fallback_structure,
        )
        structure = structure_value or fallback_structure
        title = getattr(registry, "title", None) or fallback_title
        return DeliveryTemplate(
            template_ref=str(registry.template_ref),
            family=template_ref.split("/")[1] if "/" in template_ref else fallback_title,
            format=ArtifactFormat(str(registry.format)),
            title=str(title),
            default_structure=tuple(str(item) for item in structure),
            template_path=str(path) if path is not None else None,
        )

    load = getattr(registry, "load", None)
    if load is None:
        raise TypeError("Template registry must define a load() method")

    try:
        loaded = load(
            template_ref,
            format=format,
            fallback_structure=fallback_structure,
        )
    except TypeError:
        loaded = load(template_ref)

    if isinstance(loaded, DeliveryTemplate):
        return loaded
    if isinstance(loaded, TemplateDefinition):
        return DeliveryTemplate(
            template_ref=loaded.template_ref,
            family=template_ref.split("/")[1] if "/" in template_ref else loaded.template_ref,
            format=format,
            title=loaded.title or fallback_title,
            default_structure=tuple(fallback_structure or loaded.skeleton_sections),
            template_path=str(loaded.source_path) if loaded.source_path is not None else None,
        )
    if hasattr(loaded, "template_ref") and hasattr(loaded, "format"):
        path = getattr(loaded, "path", None)
        structure = loaded.structure if hasattr(loaded, "structure") else fallback_structure
        return DeliveryTemplate(
            template_ref=str(loaded.template_ref),
            family=template_ref.split("/")[1] if "/" in template_ref else fallback_title,
            format=ArtifactFormat(str(loaded.format)),
            title=fallback_title,
            default_structure=tuple(structure),
            template_path=str(path) if path is not None else None,
        )
    raise TypeError(f"Unsupported template object: {type(loaded)!r}")
