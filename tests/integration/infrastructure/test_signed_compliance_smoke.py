from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    ContentPolicy,
    DeliveryArtifact,
    DeliveryChannel,
    DeliveryDispatchMode,
    DeliveryPack,
)
from ds_agent.infrastructure.delivery import (
    ComplianceAdapter,
    SimulatedChannelAdapter,
    build_default_channel_adapters,
)

pytestmark = [pytest.mark.integration, pytest.mark.nightly]

_ENABLE_ENV = "DS_AGENT_RUN_SIGNED_DELIVERY_SMOKE"
_ENABLED_VALUES = {"1", "true", "yes", "on"}


def _smoke_enabled() -> bool:
    return os.getenv(_ENABLE_ENV, "").strip().lower() in _ENABLED_VALUES


@pytest.fixture(scope="module", autouse=True)
def require_signed_delivery_smoke_enabled() -> None:
    if not _smoke_enabled():
        pytest.skip(
            "signed delivery smoke coverage is disabled. "
            f"Set {_ENABLE_ENV}=1 to run these tests."
        )
    if not os.getenv("DS_AGENT_COMPLIANCE_ENDPOINT"):
        pytest.fail(
            "signed delivery smoke coverage was enabled, but DS_AGENT_COMPLIANCE_ENDPOINT "
            "is not configured."
        )
    if os.getenv("DS_AGENT_COMPLIANCE_ENABLED", "").strip().lower() not in _ENABLED_VALUES:
        pytest.fail(
            "signed delivery smoke coverage was enabled, but DS_AGENT_COMPLIANCE_ENABLED "
            "is not truthy."
        )


def test_real_signed_compliance_adapter_smoke(tmp_path: Path) -> None:
    artifact_path = tmp_path / "audit-smoke.pdf"
    artifact_path.write_bytes(b"%PDF-1.7\n")

    adapter = build_default_channel_adapters(os.environ)[DeliveryChannel.COMPLIANCE_SYSTEM]
    if isinstance(adapter, SimulatedChannelAdapter):
        pytest.fail(
            "Expected a real compliance adapter when signed delivery smoke coverage is enabled."
        )
    assert isinstance(adapter, ComplianceAdapter)

    artifact = DeliveryArtifact(
        artifact_id="art-audit-smoke",
        type=ArtifactType.AUDIT_TRAIL,
        audience=AudienceKind.AUDITOR,
        format=ArtifactFormat.PDF,
        content_policy=ContentPolicy(
            structure=["data_provenance", "policy_compliance", "approval_chain"],
            tone="neutral",
            speculative_claims="forbidden",
        ),
        template_ref="tpl/audit/v1",
        delivery_channel=[DeliveryChannel.COMPLIANCE_SYSTEM],
        dispatch_mode=DeliveryDispatchMode.AUTO_WITH_SIGNATURE,
        rendered_uri=str(artifact_path),
    )
    pack = DeliveryPack(
        pack_id="DP-SMOKE-1",
        task_id="TC-SMOKE-001",
        generated_at=datetime.now(UTC),
        artifacts=[artifact],
        source_analysis_id="AUDIT-SMOKE-001",
        global_context={
            "compliance_case_id": os.getenv("DS_AGENT_COMPLIANCE_CASE_ID", "smoke-case"),
            "approval_chain": "smoke_owner, smoke_risk",
            "policy_compliance": "signed smoke submission",
        },
        signed_by=os.getenv("DS_AGENT_COMPLIANCE_SIGNER", "ds-agent-smoke"),
        signature=os.getenv("DS_AGENT_COMPLIANCE_SIGNATURE", "signed-smoke-payload"),
    )

    receipt = adapter.send(
        pack=pack,
        artifact=artifact,
        channel=DeliveryChannel.COMPLIANCE_SYSTEM,
    )

    assert receipt
