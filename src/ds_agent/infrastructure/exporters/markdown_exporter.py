"""Markdown delivery exporter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    DeliveryArtifact,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
    RenderedChart,
)


class MarkdownExporter:
    """Serialize one narrative artifact to markdown."""

    supported_format = ArtifactFormat.MARKDOWN

    def export(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
        charts: Sequence[RenderedChart],
        verification: NarrativeVerification,
        output_dir: Path,
        template: DeliveryTemplate,
        pack: object | None = None,
    ) -> Path:
        del pack
        del analysis, charts
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {template.title}", ""]
        for block in narrative.blocks:
            lines.append(f"## {block.section}: {block.title}")
            lines.append("")
            lines.append(block.body_md.strip())
            lines.append("")
            if block.citations:
                lines.append(f"_Citations: {', '.join(block.citations)}_")
                lines.append("")
        if verification.flagged_claims:
            lines.append("## Verifier Flags")
            lines.append("")
            lines.extend(f"- {claim}" for claim in verification.flagged_claims)
            lines.append("")
        if verification.report_id:
            lines.append(f"_Verifier report: {verification.report_id}_")
            lines.append("")
        target = output_dir / f"{artifact.artifact_id}.md"
        target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return target
