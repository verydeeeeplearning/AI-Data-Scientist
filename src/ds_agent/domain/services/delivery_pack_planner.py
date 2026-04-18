"""Helpers for turning task-contract deliverables into typed delivery artifacts."""

from __future__ import annotations

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    ArtifactType,
    AudienceKind,
    DeliveryArtifact,
    DeliveryChannel,
    DeliveryPack,
    _default_content_policy,
    _default_dispatch_mode,
    _default_template_ref,
)
from ds_agent.domain.entities.task_contract import DeliverableSpec


def plan_delivery_artifact(
    deliverable: DeliverableSpec,
    *,
    artifact_id: str,
) -> DeliveryArtifact:
    """Map one task-contract deliverable into a stakeholder artifact spec."""

    artifact_type = ArtifactType(deliverable.type)
    audience = _coerce_audience(deliverable.audience)
    artifact_format = _coerce_format(deliverable.format)
    return DeliveryArtifact(
        artifact_id=artifact_id,
        type=artifact_type,
        audience=audience,
        format=artifact_format,
        content_policy=_default_content_policy(artifact_type, audience),
        template_ref=_default_template_ref(artifact_type),
        delivery_channel=_default_delivery_channels(audience),
        dispatch_mode=_default_dispatch_mode(audience),
    )


def delivery_pack_audiences(pack: DeliveryPack) -> list[str]:
    """Return stable audience ordering for summaries and tool payloads."""

    return [artifact.audience.value for artifact in pack.artifacts]


def _coerce_audience(value: str) -> AudienceKind:
    normalized = str(value).strip().lower().replace("-", "_")
    aliases = {
        "peer_ds": AudienceKind.DS_PEER.value,
        "junior_mentor": AudienceKind.JUNIOR_MENTEE.value,
    }
    return AudienceKind(aliases.get(normalized, normalized))


def _coerce_format(value: str) -> ArtifactFormat:
    normalized = str(value).strip().lower()
    aliases = {
        "md": ArtifactFormat.MARKDOWN.value,
    }
    return ArtifactFormat(aliases.get(normalized, normalized))


def _default_delivery_channels(audience: AudienceKind) -> list[DeliveryChannel]:
    mapping = {
        AudienceKind.EXECUTIVE: [DeliveryChannel.EMAIL, DeliveryChannel.SLACK_DM],
        AudienceKind.PM: [DeliveryChannel.SLACK_CHANNEL, DeliveryChannel.NOTION_PAGE],
        AudienceKind.DS_PEER: [DeliveryChannel.GIT_PR],
        AudienceKind.ML_ENGINEER: [DeliveryChannel.CONFLUENCE, DeliveryChannel.JIRA_TICKET],
        AudienceKind.AUDITOR: [DeliveryChannel.COMPLIANCE_SYSTEM],
        AudienceKind.JUNIOR_MENTEE: [DeliveryChannel.NOTION_PAGE],
        AudienceKind.SENIOR_STAFF: [DeliveryChannel.CONFLUENCE],
        AudienceKind.OPS: [DeliveryChannel.SLACK_CHANNEL],
        AudienceKind.CUSTOMER: [DeliveryChannel.EMAIL],
    }
    return list(mapping[audience])
