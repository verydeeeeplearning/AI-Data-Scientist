from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

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
    DeliveryPolicyEngine,
    DeliveryRouter,
    JsonlDeliveryDispatchLog,
    SqliteDeliveryDispatchLog,
    build_default_channel_adapters,
)
from ds_agent.runtime.delivery_policy_store import DeliveryPolicy, JsonDeliveryPolicyStore


def test_delivery_router_dispatches_and_deduplicates(tmp_path) -> None:
    pack = _executive_pack()
    log = JsonlDeliveryDispatchLog(tmp_path)
    router = DeliveryRouter(
        adapters=build_default_channel_adapters(),
        policy=DeliveryPolicyEngine(default_policy=DeliveryPolicy()),
        log=log,
    )

    first = router.dispatch(
        pack=pack,
        approve_manual_review=True,
    )
    second = router.dispatch(
        pack=pack,
        approve_manual_review=True,
    )

    assert first.dispatch_status == "dispatched"
    assert first.sent_count == 2
    assert second.dispatch_status == "dispatched"
    assert second.duplicate_count == 2
    assert len(log.list_for_pack(pack.pack_id)) == 4


def test_delivery_router_blocks_auditor_without_signature(tmp_path) -> None:
    pack = DeliveryPack(
        pack_id="DP-100",
        task_id="TC-2026-100",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        confidence=0.95,
        signed_by="ds-agent@test",
        artifacts=[
            DeliveryArtifact(
                artifact_id="art-audit",
                type=ArtifactType.AUDIT_TRAIL,
                audience=AudienceKind.AUDITOR,
                format=ArtifactFormat.PDF,
                content_policy=ContentPolicy(
                    structure=["data_provenance", "policy_compliance"],
                    tone="neutral",
                    speculative_claims="forbidden",
                ),
                template_ref="tpl/audit/v1",
                delivery_channel=[DeliveryChannel.COMPLIANCE_SYSTEM],
                dispatch_mode=DeliveryDispatchMode.AUTO_WITH_SIGNATURE,
                rendered_uri="reports/audit.pdf",
            )
        ],
        status="rendered",
    )
    router = DeliveryRouter(
        adapters=build_default_channel_adapters(),
        policy=DeliveryPolicyEngine(default_policy=DeliveryPolicy()),
        log=JsonlDeliveryDispatchLog(tmp_path),
    )

    result = router.dispatch(pack=pack)

    assert result.dispatch_status == "blocked"
    assert result.blocked_count == 1
    assert result.receipts[0].reason == "signature_required"


def test_delivery_router_allows_mission_required_jira_channel_override(tmp_path) -> None:
    base_pack = _executive_pack()
    pack = base_pack.model_copy(
        update={
            "global_context": {"mission_required_delivery_channels": "jira_ticket"},
            "artifacts": [
                base_pack.artifacts[0].model_copy(
                    update={
                        "delivery_channel": [
                            DeliveryChannel.EMAIL,
                            DeliveryChannel.SLACK_DM,
                            DeliveryChannel.JIRA_TICKET,
                        ]
                    }
                )
            ],
        }
    )
    router = DeliveryRouter(
        adapters=build_default_channel_adapters(),
        policy=DeliveryPolicyEngine(default_policy=DeliveryPolicy()),
        log=JsonlDeliveryDispatchLog(tmp_path),
    )

    result = router.dispatch(
        pack=pack,
        artifact_ids={"art-exec"},
        channels={DeliveryChannel.JIRA_TICKET},
        approve_manual_review=True,
    )

    assert result.dispatch_status == "dispatched"
    assert result.sent_count == 1
    assert result.receipts[0].channel is DeliveryChannel.JIRA_TICKET
    assert result.receipts[0].status == "sent"


def test_jsonl_delivery_log_query_filters_newest_first(tmp_path) -> None:
    log = JsonlDeliveryDispatchLog(tmp_path)
    log.append(
        _log_entry(
            task_id="TC-1",
            pack_id="DP-1",
            artifact_id="A-1",
            channel="email",
            status="sent",
            idempotency_key="1",
        )
    )
    log.append(
        _log_entry(
            task_id="TC-1",
            pack_id="DP-1",
            artifact_id="A-2",
            channel="slack_dm",
            status="blocked",
            idempotency_key="2",
        )
    )
    log.append(
        _log_entry(
            task_id="TC-2",
            pack_id="DP-2",
            artifact_id="A-9",
            channel="email",
            status="sent",
            idempotency_key="9",
        )
    )

    result = log.query(
        task_id="TC-1",
        pack_id="DP-1",
        channels={DeliveryChannel.SLACK_DM, DeliveryChannel.EMAIL},
        limit=2,
    )

    assert result.returned == 2
    assert result.records[0].artifact_id == "A-2"
    assert result.records[1].artifact_id == "A-1"
    assert {record.channel.value for record in result.records} == {"slack_dm", "email"}


def test_jsonl_delivery_log_summarize_uses_pack_state(tmp_path) -> None:
    pack = _executive_pack()
    log = JsonlDeliveryDispatchLog(tmp_path)
    log.append(
        _log_entry(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            artifact_id="art-exec",
            channel="email",
            status="sent",
            idempotency_key="1",
        )
    )
    log.append(
        _log_entry(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            artifact_id="art-exec",
            channel="slack_dm",
            status="duplicate",
            idempotency_key="2",
        )
    )

    summary = log.summarize(pack=pack)

    assert summary.pack_id == pack.pack_id
    assert summary.pack_status == "rendered"
    assert summary.artifact_count == 1
    assert summary.rendered_count == 1
    assert summary.sent == 1
    assert summary.duplicate == 1
    assert summary.last_attempt is not None


def test_sqlite_delivery_log_summarize_reads_view_when_available(tmp_path) -> None:
    db_path = tmp_path / "delivery.db"
    log = SqliteDeliveryDispatchLog(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS delivery_packs (
                pack_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
            CREATE VIEW IF NOT EXISTS v_delivery_summary AS
            SELECT
                p.pack_id AS pack_id,
                p.task_id AS task_id,
                json_extract(p.payload_json, '$.status') AS status,
                COALESCE(json_array_length(p.payload_json, '$.artifacts'), 0) AS artifact_count,
                COALESCE(
                    (
                        SELECT COUNT(1)
                        FROM json_each(p.payload_json, '$.artifacts') AS artifact
                        WHERE json_extract(artifact.value, '$.rendered_uri') IS NOT NULL
                    ),
                    0
                ) AS rendered_count,
                (
                    SELECT MAX(attempted_at)
                    FROM delivery_log l
                    WHERE l.pack_id = p.pack_id
                ) AS last_attempt
            FROM delivery_packs p;
            """
        )
        conn.execute(
            """
            INSERT INTO delivery_packs(pack_id, task_id, payload_json, generated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "DP-1",
                "TC-2026-001",
                """
                {"status":"dispatched","artifacts":[{"rendered_uri":"reports/exec_brief.pptx"}]}
                """,
                "2026-04-16T00:00:00+00:00",
            ),
        )
        conn.commit()

    log.append(
        _log_entry(
            task_id="TC-2026-001",
            pack_id="DP-1",
            artifact_id="art-exec",
            channel="email",
            status="sent",
            idempotency_key="1",
        )
    )
    pack = _executive_pack().model_copy(update={"status": "dispatched"})

    summary = log.summarize(pack=pack)

    assert summary.pack_status == "dispatched"
    assert summary.artifact_count == 1
    assert summary.rendered_count == 1
    assert summary.sent == 1
    assert summary.last_attempt is not None


def test_delivery_router_applies_project_override_policy(tmp_path) -> None:
    pack = _executive_pack().model_copy(
        update={
            "tenant": "tenant-alpha",
            "global_context": {"project": "project-zeta"},
        }
    )
    store = JsonDeliveryPolicyStore(tmp_path)
    store.update_tenant_override("tenant-alpha", {"artifact_auto_delivery_enabled": True})
    store.update_project_override("project-zeta", {"artifact_auto_delivery_enabled": False})
    router = DeliveryRouter(
        adapters=build_default_channel_adapters(),
        policy=DeliveryPolicyEngine(policy_store=store),
        log=JsonlDeliveryDispatchLog(tmp_path),
    )

    result = router.dispatch(
        pack=pack,
        approve_manual_review=True,
    )

    assert result.dispatch_status == "blocked"
    assert result.blocked_count == 2
    assert {receipt.reason for receipt in result.receipts} == {"artifact_auto_delivery_disabled"}


def _executive_pack() -> DeliveryPack:
    return DeliveryPack(
        pack_id="DP-1",
        task_id="TC-2026-001",
        generated_at=datetime(2026, 4, 16, tzinfo=UTC),
        confidence=0.82,
        signed_by="ds-agent@test",
        artifacts=[
            DeliveryArtifact(
                artifact_id="art-exec",
                type=ArtifactType.EXEC_BRIEF,
                audience=AudienceKind.EXECUTIVE,
                format=ArtifactFormat.PPTX,
                content_policy=ContentPolicy(
                    structure=["situation", "impact", "decision_needed"],
                    tone="decisive",
                    technical_detail="minimal",
                    chart_count_range=(2, 3),
                ),
                template_ref="tpl/exec_brief/v3",
                delivery_channel=[DeliveryChannel.EMAIL, DeliveryChannel.SLACK_DM],
                dispatch_mode=DeliveryDispatchMode.MANUAL_REVIEW,
                rendered_uri="reports/exec_brief.pptx",
            )
        ],
        status="rendered",
    )


def _log_entry(
    *,
    task_id: str,
    pack_id: str,
    artifact_id: str,
    channel: str,
    status: str,
    idempotency_key: str,
):
    from ds_agent.infrastructure.delivery import DeliveryLogEntry

    return DeliveryLogEntry(
        task_id=task_id,
        pack_id=pack_id,
        artifact_id=artifact_id,
        channel=channel,
        status=status,
        idempotency_key=idempotency_key,
        recorded_at=datetime(2026, 4, 16, tzinfo=UTC).isoformat(),
    )
