from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.external_reference import (
    ExternalReference,
    build_integration_idempotency_key,
)


def test_idempotency_key_builder_is_stable_and_unique() -> None:
    key_a = build_integration_idempotency_key(
        work_object_id="WO-2026-001",
        system="jira",
        action="create_issue",
        discriminator="abc123",
    )
    key_b = build_integration_idempotency_key(
        work_object_id="WO-2026-001",
        system="jira",
        action="create_issue",
        discriminator="abc123",
    )
    key_c = build_integration_idempotency_key(
        work_object_id="WO-2026-001",
        system="jira",
        action="create_issue",
        discriminator="def456",
    )

    assert key_a == key_b
    assert key_a != key_c


def test_external_reference_identity_includes_system_type_and_resource() -> None:
    reference = ExternalReference(
        system="slack",
        resource_type="thread",
        resource_id="171234.1000",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        idempotency_key="wo_WO-2026-001:slack:post_message:abc123",
    )

    assert reference.identity == "slack:thread:171234.1000"
