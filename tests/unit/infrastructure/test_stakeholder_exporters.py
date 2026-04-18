from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import nbformat

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    ContentPolicy,
    DeliveryArtifact,
    DeliveryPack,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
)
from ds_agent.infrastructure.artifact.stakeholder_exporters import (
    IpynbArtifactExporter,
    MarkdownArtifactExporter,
)


def _artifact(
    artifact_id: str,
    artifact_type: ArtifactType,
    artifact_format: ArtifactFormat,
) -> DeliveryArtifact:
    audience = (
        AudienceKind.DS_PEER
        if artifact_format == ArtifactFormat.IPYNB
        else AudienceKind.PM
    )
    return DeliveryArtifact(
        artifact_id=artifact_id,
        type=artifact_type,
        audience=audience,
        format=artifact_format,
        content_policy=ContentPolicy(structure=["summary"], tone="precise"),
        template_ref="tpl/test/v1",
    )


def _pack(artifact: DeliveryArtifact) -> DeliveryPack:
    return DeliveryPack(
        pack_id="DP-1",
        task_id="TC-2026-001",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        artifacts=[artifact],
    )


def _narrative() -> NarrativeBlocks:
    return NarrativeBlocks.model_validate(
        {
            "blocks": [
                {
                    "section": "summary",
                    "title": "Summary",
                    "body_md": "Top finding",
                    "citations": ["lineage-1"],
                }
            ],
            "overall_tone": "precise",
            "flagged_claims": ["needs review"],
        }
    )


def test_markdown_exporter_writes_sections_and_flags(tmp_path: Path) -> None:
    artifact = _artifact("art-pm", ArtifactType.PM_ACTION_MEMO, ArtifactFormat.MARKDOWN)
    path = MarkdownArtifactExporter().export(
        artifact=artifact,
        analysis={"summary": "Top finding"},
        narrative=_narrative(),
        charts=[],
        verification=NarrativeVerification(
            report_id="vr-1",
            flagged_claims=["needs review"],
        ),
        template=DeliveryTemplate(
            template_ref=artifact.template_ref,
            family="test",
            format=ArtifactFormat.MARKDOWN,
            title="Template",
            default_structure=("summary",),
        ),
        output_dir=tmp_path,
        pack=_pack(artifact),
    )

    content = path.read_text(encoding="utf-8")
    assert "## Summary" in content
    assert "Verifier Flags" in content


def test_ipynb_exporter_creates_valid_notebook(tmp_path: Path) -> None:
    artifact = _artifact("art-ds", ArtifactType.DS_EXPERIMENT_NOTE, ArtifactFormat.IPYNB)
    path = IpynbArtifactExporter().export(
        artifact=artifact,
        analysis={"summary": "Top finding"},
        narrative=_narrative(),
        charts=[],
        verification=NarrativeVerification(
            report_id="vr-1",
            flagged_claims=["needs review"],
        ),
        template=DeliveryTemplate(
            template_ref=artifact.template_ref,
            family="test",
            format=ArtifactFormat.IPYNB,
            title="Template",
            default_structure=("summary",),
        ),
        output_dir=tmp_path,
        pack=_pack(artifact),
    )

    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    assert notebook.cells[0].cell_type == "markdown"
    assert "Summary" in notebook.cells[0].source
