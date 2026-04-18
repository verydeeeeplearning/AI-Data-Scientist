"""Notebook delivery exporter."""

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
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine


class IpynbExporter:
    """Serialize narrative blocks into a lightweight notebook artifact."""

    supported_format = ArtifactFormat.IPYNB

    def __init__(self, engine: NotebookEngine | None = None) -> None:
        self._engine = engine or NotebookEngine()

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
        del charts
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_blocks = [f"# {template.title}"]
        for block in narrative.blocks:
            markdown_blocks.append(f"## {block.title}\n\n{block.body_md.strip()}")
        if verification.flagged_claims:
            markdown_blocks.append(
                "## Verifier Flags\n\n"
                + "\n".join(f"- {claim}" for claim in verification.flagged_claims)
            )
        if artifact.content_policy.include_verifier_results and verification.report_id:
            markdown_blocks.append(f"## Verifier Report\n\n- report_id: {verification.report_id}")
        code_blocks = [
            str(item)
            for item in analysis.get("code_blocks", [])
            if isinstance(item, str)
        ]
        output_blocks = [
            str(item)
            for item in analysis.get("output_blocks", [])
            if isinstance(item, str)
        ]
        if artifact.content_policy.include_code and not code_blocks:
            code_blocks = ["# Analysis payload did not include code_blocks."]
        target = output_dir / f"{artifact.artifact_id}.ipynb"
        self._engine.write(
            str(target),
            markdown_blocks=markdown_blocks,
            code_blocks=code_blocks,
            output_blocks=output_blocks,
        )
        return target
