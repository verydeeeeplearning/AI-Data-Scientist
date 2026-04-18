"""Template resolution for stakeholder communication artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ds_agent.domain.entities.delivery_pack import ArtifactFormat, DeliveryTemplate


class StaticTemplateRegistry:
    """Resolve local template refs with sensible fallbacks."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self._root_dir = (
            Path(root_dir)
            if root_dir is not None
            else Path(__file__).resolve().parents[4] / "assets" / "templates"
        )

    def load(
        self,
        template_ref: str,
        *,
        format: ArtifactFormat,
        fallback_structure: Sequence[str],
    ) -> DeliveryTemplate:
        parts = template_ref.split("/")
        family = parts[1] if len(parts) == 3 else "default"
        template_path = self._resolve_path(template_ref, format)
        return DeliveryTemplate(
            template_ref=template_ref,
            family=family,
            format=format,
            title=family.replace("_", " ").title(),
            default_structure=tuple(fallback_structure),
            template_path=str(template_path) if template_path is not None else None,
        )

    def _resolve_path(self, template_ref: str, format: ArtifactFormat) -> Path | None:
        parts = template_ref.split("/")
        if len(parts) != 3 or parts[0] != "tpl":
            return None
        family = parts[1]
        version = parts[2]
        suffix_map = {
            ArtifactFormat.PPTX: ".pptx",
            ArtifactFormat.MARKDOWN: ".md",
            ArtifactFormat.IPYNB: ".ipynb",
            ArtifactFormat.PDF: ".pdf.jinja",
            ArtifactFormat.DOCX: ".docx",
            ArtifactFormat.HTML: ".html",
            ArtifactFormat.XLSX: ".xlsx",
        }
        suffix = suffix_map.get(format)
        if suffix is None:
            return None
        candidate = self._root_dir / family / f"{version}{suffix}"
        if candidate.exists():
            return candidate
        return None
