from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PyPDF2 import PdfReader

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    ContentPolicy,
    DeliveryArtifact,
    DeliveryDispatchMode,
    DeliveryPack,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
    SpeculativeClaimsPolicy,
)
from ds_agent.infrastructure.exporters.pdf_exporter import PdfExporter


def test_pdf_exporter_creates_pdf_artifact(tmp_path: Path) -> None:
    artifact = DeliveryArtifact(
        artifact_id="art-audit",
        type=ArtifactType.AUDIT_TRAIL,
        audience=AudienceKind.AUDITOR,
        format=ArtifactFormat.PDF,
        content_policy=ContentPolicy(
            structure=["data_provenance", "policy_compliance", "approval_chain"],
            tone="neutral",
            technical_detail="balanced",
            speculative_claims=SpeculativeClaimsPolicy.FORBIDDEN,
        ),
        template_ref="tpl/audit/v1",
        dispatch_mode=DeliveryDispatchMode.AUTO_WITH_SIGNATURE,
    )
    pack = DeliveryPack(
        pack_id="DP-1",
        task_id="TC-2026-001",
        source_analysis_id="fa-1",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        signed_by="auditor@test",
        signature="signed-blob",
        artifacts=[artifact],
    )
    narrative = NarrativeBlocks.model_validate(
        {
            "blocks": [
                {
                    "section": "data_provenance",
                    "title": "Data Provenance",
                    "body_md": "- Source: warehouse.curated_churn\n- Extracted: 2026-04-16",
                    "citations": ["lineage-1"],
                },
                {
                    "section": "policy_compliance",
                    "title": "Policy Compliance",
                    "body_md": "- Retention label verified\n- Access pattern reviewed",
                    "citations": ["policy-7"],
                },
            ],
            "overall_tone": "neutral",
            "flagged_claims": [],
        }
    )

    output = PdfExporter().export(
        artifact=artifact,
        analysis={"summary": "Audit ready"},
        narrative=narrative,
        charts=[],
        verification=NarrativeVerification(report_id="vr-audit"),
        template=DeliveryTemplate(
            template_ref=artifact.template_ref,
            family="audit",
            format=ArtifactFormat.PDF,
            title="Audit Trail",
            default_structure=("data_provenance", "policy_compliance", "approval_chain"),
        ),
        output_dir=tmp_path,
        pack=pack,
    )

    assert output.suffix == ".pdf"
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
    extracted = PdfReader(str(output)).pages[0].extract_text()
    assert "Audit Trail" in extracted
    assert "Read-only compliance artifact." in extracted
    assert "Signature: signed-blob" in extracted
    assert "Verifier report: vr-audit" in extracted
    assert "Data Provenance" in extracted
