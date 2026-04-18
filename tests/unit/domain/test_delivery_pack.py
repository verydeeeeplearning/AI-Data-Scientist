from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    ContentPolicy,
    DeliveryArtifact,
    DeliveryDispatchMode,
    DeliveryPack,
    SpeculativeClaimsPolicy,
)


def _artifact(
    *,
    artifact_id: str,
    audience: AudienceKind,
    artifact_type: ArtifactType = ArtifactType.EXEC_BRIEF,
    artifact_format: ArtifactFormat = ArtifactFormat.PPTX,
    rendered_uri: str | None = None,
) -> DeliveryArtifact:
    policy = ContentPolicy(
        structure=["summary", "finding"],
        speculative_claims=(
            SpeculativeClaimsPolicy.FORBIDDEN
            if audience == AudienceKind.AUDITOR
            else SpeculativeClaimsPolicy.FLAGGED
        ),
        chart_count_range=(1, 2) if audience == AudienceKind.EXECUTIVE else None,
    )
    return DeliveryArtifact(
        artifact_id=artifact_id,
        type=artifact_type,
        audience=audience,
        format=artifact_format,
        content_policy=policy,
        template_ref="tpl/test/v1",
        dispatch_mode=(
            DeliveryDispatchMode.AUTO_WITH_SIGNATURE
            if audience == AudienceKind.AUDITOR
            else DeliveryDispatchMode.MANUAL_REVIEW
        ),
        rendered_uri=rendered_uri,
    )


def test_delivery_pack_rejects_duplicate_audience_artifacts() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    with pytest.raises(ValueError, match="Duplicate delivery artifact audience"):
        DeliveryPack(
            pack_id="DP-1",
            task_id="TC-2026-001",
            generated_at=now,
            artifacts=[
                _artifact(artifact_id="art-1", audience=AudienceKind.EXECUTIVE),
                _artifact(artifact_id="art-2", audience=AudienceKind.EXECUTIVE),
            ],
        )


def test_delivery_pack_enforces_auditor_policy() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    bad_auditor_artifact = DeliveryArtifact(
        artifact_id="art-audit",
        type=ArtifactType.AUDIT_TRAIL,
        audience=AudienceKind.AUDITOR,
        format=ArtifactFormat.PDF,
        content_policy=ContentPolicy(
            structure=["lineage"],
            speculative_claims=SpeculativeClaimsPolicy.FLAGGED,
        ),
        template_ref="tpl/audit/v1",
        dispatch_mode=DeliveryDispatchMode.MANUAL_REVIEW,
    )
    with pytest.raises(ValueError, match="auditor artifacts require speculative_claims=forbidden"):
        DeliveryPack(
            pack_id="DP-2",
            task_id="TC-2026-001",
            generated_at=now,
            artifacts=[bad_auditor_artifact],
        )


def test_delivery_pack_derives_legacy_items_from_rendered_artifacts() -> None:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    pack = DeliveryPack(
        pack_id="DP-3",
        task_id="TC-2026-001",
        generated_at=now,
        artifacts=[
            _artifact(
                artifact_id="art-exec",
                audience=AudienceKind.EXECUTIVE,
                rendered_uri="reports/exec_brief.pptx",
            )
        ],
    )

    assert len(pack.items) == 1
    assert pack.items[0].artifact_id == "art-exec"
    assert pack.items[0].artifact_path == "reports/exec_brief.pptx"
    assert pack.items[0].delivered is True
