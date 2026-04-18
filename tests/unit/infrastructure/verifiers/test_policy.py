from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult
from ds_agent.domain.entities.task_contract import DataSourceGrant, TaskContract
from ds_agent.infrastructure.verifiers.policy import PolicyVerifier


def _task_contract() -> TaskContract:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        business_goal="Reduce churn",
        allowed_data_sources=[DataSourceGrant(warehouse="snowflake", schema="analytics")],
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        created_at=now,
        updated_at=now,
    )


def _base_artifacts() -> dict[str, object]:
    return {
        "deliverable_payload": {"headline": "Weekly summary", "owner": "ops"},
        "pii_policy": "mask",
        "run_log": [
            {"type": "source_access", "source": "snowflake.analytics"},
            {"cost_usd": 2.0},
        ],
        "cost_budget_usd": 10.0,
        "risk_level": "medium",
        "retention_items": [
            {"artifact": "report.pdf", "retention_label": "30d", "storage_retention": "30d"}
        ],
    }


def _ctx(overrides: dict[str, object] | None = None) -> VerifierContext:
    artifacts = _base_artifacts()
    if overrides:
        artifacts.update(overrides)
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        artifacts=artifacts,
        config=VerifierConfig(),
    )


def _find_check(verifier_result, check_id: str) -> CheckResult:
    return next(check for check in verifier_result.checks if check.check_id == check_id)


@pytest.mark.asyncio
async def test_pii_exposure_fails_when_payload_contains_unmasked_email() -> None:
    result = await PolicyVerifier().run(
        _ctx({"deliverable_payload": {"email": "alice@example.com"}, "pii_policy": "mask"})
    )

    check = _find_check(result, "pii_exposure")

    assert check.status == "fail"
    assert check.evidence["matches"]


@pytest.mark.asyncio
async def test_access_scope_fails_for_unapproved_source() -> None:
    result = await PolicyVerifier().run(
        _ctx(
            {
                "run_log": [
                    {"type": "source_access", "source": "snowflake.analytics"},
                    {"type": "source_access", "source": "bigquery.private"},
                ]
            }
        )
    )

    check = _find_check(result, "access_scope")

    assert check.status == "fail"
    assert "bigquery.private" in check.evidence["violations"]


@pytest.mark.asyncio
async def test_cost_budget_warns_near_budget_limit() -> None:
    result = await PolicyVerifier().run(
        _ctx({"run_log": [{"cost_usd": 8.5}], "cost_budget_usd": 10.0})
    )

    check = _find_check(result, "cost_budget_compliance")

    assert check.status == "warn"


@pytest.mark.asyncio
async def test_risky_action_detection_fails_when_low_risk_allows_no_destructive_actions() -> None:
    result = await PolicyVerifier().run(
        _ctx({"run_log": [{"action": "drop_table"}], "risk_level": "low"})
    )

    check = _find_check(result, "risky_action_detection")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_retention_policy_fails_on_missing_label() -> None:
    result = await PolicyVerifier().run(
        _ctx({"retention_items": [{"artifact": "report.pdf", "storage_retention": "30d"}]})
    )

    check = _find_check(result, "retention_policy")

    assert check.status == "fail"


@pytest.mark.asyncio
async def test_write_side_effect_preview_warns_without_preview() -> None:
    result = await PolicyVerifier().run(
        _ctx(
            {
                "run_log": [
                    {
                        "type": "write",
                        "target": "analytics.table",
                        "preview_available": False,
                    }
                ]
            }
        )
    )

    check = _find_check(result, "write_side_effect_preview")

    assert check.status == "warn"
