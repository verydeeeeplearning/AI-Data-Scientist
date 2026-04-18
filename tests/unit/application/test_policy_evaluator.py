"""Tests for policy-based approval evaluation and hook integration."""

from __future__ import annotations

import pytest

from ds_agent.agent.governance_hooks import PolicyApprovalHook
from ds_agent.agent.hooks import HookAction, HookContext
from ds_agent.application.services.policy_evaluator import PolicyEvaluator
from ds_agent.domain.entities.approval_policy import (
    ApprovalPolicy,
    DataSensitivity,
    PolicyDecisionType,
    PolicyRule,
)
from ds_agent.runtime.approval_store import JsonApprovalStore


def _make_evaluator(tmp_path) -> PolicyEvaluator:
    policy = ApprovalPolicy(
        rules=[
            PolicyRule(
                action_pattern="sql_query",
                data_sensitivity=DataSensitivity.PII,
                environment="prod",
                decision=PolicyDecisionType.APPROVAL,
            ),
            PolicyRule(
                action_pattern="file_read",
                data_sensitivity=DataSensitivity.PUBLIC,
                decision=PolicyDecisionType.AUTO,
            ),
            PolicyRule(
                action_pattern="deploy_model",
                environment="prod",
                confidence_threshold=0.7,
                decision=PolicyDecisionType.APPROVAL,
            ),
            PolicyRule(
                action_pattern="delete*",
                decision=PolicyDecisionType.DOUBLE_CHECK,
            ),
            PolicyRule(action_pattern="*", decision=PolicyDecisionType.AUTO),
        ]
    )
    return PolicyEvaluator(
        policy=policy,
        storage_path=str(tmp_path / "standing_approvals.json"),
    )


class TestPolicyEvaluator:
    def test_requires_approval_for_pii_sql_in_prod(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        decision = evaluator.evaluate(
            "sql_query",
            sensitivity="pii",
            env="prod",
            confidence=1.0,
        )
        assert decision.decision == PolicyDecisionType.APPROVAL

    def test_auto_approves_public_file_read(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        decision = evaluator.evaluate("file_read", sensitivity="public", env="dev")
        assert decision.decision == PolicyDecisionType.AUTO

    def test_promotes_to_standing_after_three_approvals(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        for _ in range(3):
            standing = evaluator.record_approval(
                "sql_query",
                approved_by="operator",
                sensitivity="pii",
                env="prod",
            )
        assert standing.promoted is True
        decision = evaluator.evaluate("sql_query", sensitivity="pii", env="prod")
        assert decision.decision == PolicyDecisionType.AUTO

    def test_low_confidence_deploy_requires_approval(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        decision = evaluator.evaluate(
            "deploy_model",
            sensitivity="internal",
            env="prod",
            confidence=0.4,
        )
        assert decision.decision == PolicyDecisionType.APPROVAL

    def test_delete_requests_double_check(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        decision = evaluator.evaluate("delete_file", sensitivity="internal", env="dev")
        assert decision.decision == PolicyDecisionType.DOUBLE_CHECK


class TestPolicyApprovalHook:
    @pytest.mark.asyncio
    async def test_creates_approval_request_for_policy_denial(self, tmp_path):
        store = JsonApprovalStore(base_dir=tmp_path)
        hook = PolicyApprovalHook(evaluator=_make_evaluator(tmp_path))
        events: list[tuple[str, dict]] = []
        context = HookContext(
            session_id="session-1",
            environment="prod",
            approval_store=store,
            emit=lambda event, payload: events.append((event, payload)),
        )

        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT email FROM users", "data_sensitivity": "pii"},
            context,
        )

        assert result.action == HookAction.DENY
        assert "approval_id=" in (result.deny_reason or "")
        assert store.pending_count == 1
        assert [event for event, _ in events] == ["policy.decision", "approval.requested"]
