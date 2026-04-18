from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ds_agent.agent.builtin_hooks import PermissionHook
from ds_agent.agent.hooks import HookAction, HookContext
from ds_agent.agent.permissions import PermissionMode, PermissionPolicy
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle


def _mission_pack() -> MissionPack:
    return MissionPack.model_validate(
        {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "boundary": {
                "allowed_data_domains": ["growth", "sales", "marketing"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["jira_create", "artifact_draft"],
            },
            "required_checks": ["schema_drift"],
            "required_artifacts": ["exec_brief"],
            "success_criteria": ["issue_classified"],
            "action_policy_overrides": {"jira_create": {"delegate": "auto"}},
        }
    )


def _bundle() -> TaskContractBundle:
    return TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="ops_triage",
            business_goal="Triage KPI anomalies",
            mission="weekly-kpi-triage",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "md"}
            ],
            created_at=datetime(2026, 4, 15, tzinfo=UTC),
            updated_at=datetime(2026, 4, 15, tzinfo=UTC),
        )
    )


@pytest.mark.asyncio
async def test_permission_hook_allows_delegate_jira_inside_mission_override() -> None:
    store = MagicMock()
    store.get_active_bundle.return_value = _bundle()
    loader = MagicMock()
    loader.try_load.return_value = _mission_pack()
    hook = PermissionHook(
        PermissionPolicy(mode=PermissionMode.FULL_ACCESS),
        task_contract_store=store,
        mission_loader=loader,
    )

    result = await hook.pre_tool_use(
        "create_jira_ticket",
        {"data_domain": "growth"},
        HookContext(mode="auto", session_id="session-1"),
    )

    assert result.action == HookAction.ALLOW


@pytest.mark.asyncio
async def test_permission_hook_denies_out_of_boundary_prod_deploy() -> None:
    store = MagicMock()
    store.get_active_bundle.return_value = _bundle()
    loader = MagicMock()
    loader.try_load.return_value = _mission_pack()
    hook = PermissionHook(
        PermissionPolicy(mode=PermissionMode.FULL_ACCESS),
        task_contract_store=store,
        mission_loader=loader,
    )

    result = await hook.pre_tool_use(
        "generate_deployment",
        {"environment": "production", "data_domain": "growth"},
        HookContext(mode="auto", session_id="session-1"),
    )

    assert result.action == HookAction.DENY
    assert result.deny_reason is not None
    assert "outside mission boundary" in result.deny_reason
