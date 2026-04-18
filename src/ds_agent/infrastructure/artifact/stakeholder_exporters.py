"""Markdown and notebook exporters for stakeholder communication artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import nbformat

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    DeliveryArtifact,
    DeliveryPack,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
    RenderedChart,
)
from ds_agent.infrastructure.exporters.pdf_exporter import PdfExporter as PdfArtifactExporter


class MarkdownArtifactExporter:
    """Write structured narrative blocks to Markdown."""

    supported_format = ArtifactFormat.MARKDOWN

    def export(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any] | None = None,
        narrative: NarrativeBlocks,
        charts: Sequence[RenderedChart] = (),
        verification: NarrativeVerification | None = None,
        output_dir: Path,
        template: DeliveryTemplate | None = None,
        pack: DeliveryPack | None = None,
    ) -> Path:
        del analysis, charts, template, pack
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {artifact.type.value.replace('_', ' ').title()}", ""]
        for block in narrative.blocks:
            lines.extend([f"## {block.title}", block.body_md, ""])
            if block.citations:
                lines.extend(
                    [
                        f"_Citations_: {', '.join(block.citations)}",
                        "",
                    ]
                )
        if verification is not None and verification.flagged_claims:
            lines.extend(
                [
                    "## Verifier Flags",
                    *[f"- {claim}" for claim in verification.flagged_claims],
                    "",
                ]
            )
        output_path = output_dir / f"{artifact.artifact_id}.md"
        output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return output_path


class IpynbArtifactExporter:
    """Write structured narrative blocks to a validated notebook."""

    supported_format = ArtifactFormat.IPYNB

    def export(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any] | None = None,
        narrative: NarrativeBlocks,
        charts: Sequence[RenderedChart] = (),
        verification: NarrativeVerification | None = None,
        output_dir: Path,
        template: DeliveryTemplate | None = None,
        pack: DeliveryPack | None = None,
    ) -> Path:
        del analysis, charts, template
        output_dir.mkdir(parents=True, exist_ok=True)
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["delivery_pack"] = {
            "pack_id": pack.pack_id if pack is not None else "DP-0",
            "artifact_id": artifact.artifact_id,
            "audience": artifact.audience.value,
        }
        for block in narrative.blocks:
            source = [f"## {block.title}", "", block.body_md]
            if block.citations:
                source.extend(["", f"Citations: {', '.join(block.citations)}"])
            notebook.cells.append(nbformat.v4.new_markdown_cell("\n".join(source)))
        if verification is not None and verification.flagged_claims:
            notebook.cells.append(
                nbformat.v4.new_markdown_cell(
                    "## Verifier Flags\n\n"
                    + "\n".join(f"- {claim}" for claim in verification.flagged_claims)
                )
            )
        nbformat.validate(notebook)
        output_path = output_dir / f"{artifact.artifact_id}.ipynb"
        output_path.write_text(nbformat.writes(notebook), encoding="utf-8")
        return output_path


def default_stakeholder_exporters() -> tuple[object, ...]:
    """Return the default stakeholder exporter set."""

    return (
        MarkdownArtifactExporter(),
        IpynbArtifactExporter(),
        PdfArtifactExporter(),
    )
