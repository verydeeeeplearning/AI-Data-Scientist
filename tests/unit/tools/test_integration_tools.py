from __future__ import annotations

import base64
import importlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.application.services.policy_evaluator import PolicyEvaluator
from ds_agent.domain.entities.approval_policy import ApprovalPolicy, PolicyDecisionType, PolicyRule
from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.infrastructure.persistence.work_object_store import SqliteWorkObjectStore
from ds_agent.infrastructure.work_object_container import build_work_object_container
from ds_agent.infrastructure.work_object_policy import EvaluatorWorkflowIntegrationPolicy
from ds_agent.tools.registry import ToolRegistry


def _bundle(task_id: str) -> TaskContractBundle:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    suffix = task_id[-3:]
    return TaskContractBundle(
        contract=TaskContract(
            task_id=task_id,
            session_id="session-1",
            type="churn_analysis",
            business_goal="Reduce churn",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            goal_brief_id=f"GB-{suffix}",
            assumption_log_id=f"AL-{suffix}",
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id=f"GB-{suffix}",
            task_id=task_id,
            business_question="Why churn?",
            ds_problem_statement="Binary classification",
            comparison_baseline="last quarter",
            decision_to_make="prioritize actions",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        assumption_log=AssumptionLog(log_id=f"AL-{suffix}", task_id=task_id),
    ).sync_references()


def _wire_integration_tool_module(
    tmp_path: Path,
    *,
    evaluator: PolicyEvaluator | None = None,
):
    module_name = "ds_agent.tools.integration_tools"
    module = sys.modules.get(module_name) or importlib.import_module(module_name)

    db_path = tmp_path / f"{uuid.uuid4().hex}.db"
    task_store = SqliteTaskContractStore(db_path)
    task_store.create_bundle(_bundle("TC-2026-001"))
    task_store.create_bundle(_bundle("TC-2026-002"))
    work_store = SqliteWorkObjectStore(db_path)
    module.set_work_object_container(
        build_work_object_container(
            store=work_store,
            task_store=task_store,
            policy=(
                None
                if evaluator is None
                else EvaluatorWorkflowIntegrationPolicy(evaluator)
            ),
        )
    )
    return module


@pytest.fixture
def integration_tool_module(tmp_path: Path):
    return _wire_integration_tool_module(tmp_path)


@pytest.mark.asyncio
async def test_work_object_tool_lifecycle(integration_tool_module) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_work_object",
            {
                "task_contract_id": "TC-2026-001",
                "title": "Weekly churn request",
                "request_source": "slack",
                "requestor_id": "U123",
                "requestor_display": "Kim",
                "original_text": "Investigate churn and summarize it.",
                "channel": "growth-ds",
            },
        )
    )
    assert created["ok"] is True
    work_object_id = created["work_object"]["work_object_id"]

    listed = json.loads(
        await ToolRegistry.dispatch(
            "list_work_objects",
            {"task_contract_id": "TC-2026-001"},
        )
    )
    assert listed["ok"] is True
    assert listed["work_objects"][0]["work_object_id"] == work_object_id

    for phase, extra in [
        ("executing", {"run_id": "run-1"}),
        ("review", {}),
    ]:
        result = json.loads(
            await ToolRegistry.dispatch(
                "advance_work_object_phase",
                {"work_object_id": work_object_id, "to_phase": phase, **extra},
            )
        )
        assert result["ok"] is True
        assert result["phase"] == phase

    linked = json.loads(
        await ToolRegistry.dispatch(
            "link_external_resource",
            {
                "work_object_id": work_object_id,
                "system": "confluence",
                "resource_type": "page",
                "resource_id": "page-1",
                "location": "documentation",
                "description": "Executive brief page",
            },
        )
    )
    assert linked["ok"] is True

    for phase in ["documenting", "followup"]:
        result = json.loads(
            await ToolRegistry.dispatch(
                "advance_work_object_phase",
                {"work_object_id": work_object_id, "to_phase": phase},
            )
        )
        assert result["ok"] is True
        assert result["phase"] == phase

    closed = json.loads(
        await ToolRegistry.dispatch(
            "close_work_object",
            {"work_object_id": work_object_id, "reason": "Stakeholder loop completed"},
        )
    )
    assert closed["ok"] is True
    assert closed["phase"] == "closed"

    fetched = json.loads(
        await ToolRegistry.dispatch("get_work_object", {"work_object_id": work_object_id})
    )
    assert fetched["ok"] is True
    assert fetched["work_object"]["execution"]["current_phase"] == "closed"
    assert fetched["work_object"]["documentation"]["references"][0]["resource_id"] == "page-1"
    assert len(fetched["timeline"]) >= 5


@pytest.mark.asyncio
async def test_slack_and_jira_tools_track_work_object(
    integration_tool_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_work_object",
            {
                "task_contract_id": "TC-2026-002",
                "title": "Follow-up automation request",
                "request_source": "electron",
                "requestor_id": "operator-1",
                "requestor_display": "Operator",
                "original_text": "Share the summary and open the ticket.",
            },
        )
    )
    work_object_id = created["work_object"]["work_object_id"]

    slack_calls: list[str] = []

    def _fake_send(
        self,
        webhook_url: str,
        *,
        text: str,
        blocks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        slack_calls.append(text)
        return {"ok": True, "response": "ok"}

    monkeypatch.setattr(
        "ds_agent.infrastructure.external.slack_client.SlackClient.send",
        _fake_send,
    )

    first_post = json.loads(
        await ToolRegistry.dispatch(
            "post_to_slack",
            {
                "work_object_id": work_object_id,
                "message": "Churn brief is ready.",
                "webhook_url": "https://example.com/slack",
            },
        )
    )
    second_post = json.loads(
        await ToolRegistry.dispatch(
            "post_to_slack",
            {
                "work_object_id": work_object_id,
                "message": "Churn brief is ready.",
                "webhook_url": "https://example.com/slack",
            },
        )
    )
    assert first_post["ok"] is True
    assert first_post["duplicate"] is False
    assert second_post["ok"] is True
    assert second_post["duplicate"] is True
    assert slack_calls == ["Churn brief is ready."]

    jira_labels: list[str] = []

    def _fake_create_issue(self, **kwargs):
        jira_labels.extend(kwargs.get("labels") or [])
        return {"key": "DS-101", "id": "10001"}

    monkeypatch.setattr(
        "ds_agent.infrastructure.external.jira_client.JiraClient.create_issue",
        _fake_create_issue,
    )
    monkeypatch.setenv("DS_AGENT_JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setenv("DS_AGENT_JIRA_EMAIL", "bot@example.com")
    monkeypatch.setenv("DS_AGENT_JIRA_API_TOKEN", "secret")

    jira_result = json.loads(
        await ToolRegistry.dispatch(
            "create_jira_ticket",
            {
                "summary": "Follow up churn actions",
                "description": "Create retention work items.",
                "project": "DS",
                "work_object_id": work_object_id,
            },
        )
    )
    assert jira_result["ok"] is True
    assert jira_result["external_ref"]["resource_id"] == "DS-101"
    assert f"wo-{work_object_id.lower()}" in jira_labels

    fetched = json.loads(
        await ToolRegistry.dispatch("get_work_object", {"work_object_id": work_object_id})
    )
    assert fetched["ok"] is True
    assert fetched["work_object"]["documentation"]["references"][0]["system"] == "slack"
    assert (
        fetched["work_object"]["follow_up"]["actions"][0]["external_ref"]["resource_id"]
        == "DS-101"
    )

    timeline = json.loads(
        await ToolRegistry.dispatch(
            "get_work_object_timeline",
            {"work_object_id": work_object_id, "limit": 20},
        )
    )
    event_actions = [event["action"] for event in timeline["events"]]
    assert "post_message" in event_actions
    assert "create_issue" in event_actions


@pytest.mark.asyncio
async def test_documentation_publish_tools_track_work_object(
    integration_tool_module,
) -> None:
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_work_object",
            {
                "task_contract_id": "TC-2026-002",
                "title": "Documentation publish request",
                "request_source": "electron",
                "requestor_id": "operator-1",
                "requestor_display": "Operator",
                "original_text": "Publish the brief and open the PR.",
            },
        )
    )
    work_object_id = created["work_object"]["work_object_id"]

    confluence = json.loads(
        await ToolRegistry.dispatch(
            "publish_confluence_page",
            {
                "work_object_id": work_object_id,
                "title": "Weekly churn brief",
                "body_markdown": "# Summary\n- Segment A",
                "space_key": "DS",
                "dry_run": True,
            },
        )
    )
    notion = json.loads(
        await ToolRegistry.dispatch(
            "publish_notion_page",
            {
                "work_object_id": work_object_id,
                "title": "Weekly churn brief",
                "body_markdown": "# Summary\n- Segment A",
                "parent_page_id": "parent-1",
                "dry_run": True,
            },
        )
    )
    git_pr = json.loads(
        await ToolRegistry.dispatch(
            "open_git_pr",
            {
                "work_object_id": work_object_id,
                "provider": "github",
                "repo": "org/repo",
                "base_branch": "main",
                "title": "Weekly churn updates",
                "body_md": "Generated by ds-agent",
                "files": [
                    {
                        "path": "analysis.sql",
                        "content_base64": base64.b64encode(b"select 1;\n").decode("ascii"),
                        "mode": "add",
                    }
                ],
                "dry_run": True,
            },
        )
    )

    assert confluence["ok"] is True
    assert confluence["external_ref"]["system"] == "confluence"
    assert notion["ok"] is True
    assert notion["external_ref"]["system"] == "notion"
    assert git_pr["ok"] is True
    assert git_pr["external_ref"]["system"] == "github"

    fetched = json.loads(
        await ToolRegistry.dispatch("get_work_object", {"work_object_id": work_object_id})
    )
    doc_systems = [item["system"] for item in fetched["work_object"]["documentation"]["references"]]
    assert doc_systems == ["confluence", "notion", "github"]

    timeline = json.loads(
        await ToolRegistry.dispatch(
            "get_work_object_timeline",
            {"work_object_id": work_object_id, "limit": 20},
        )
    )
    event_actions = [event["action"] for event in timeline["events"]]
    assert event_actions[-3:] == ["publish_page", "publish_page", "open_pull_request"]


@pytest.mark.asyncio
async def test_policy_gated_dispatch_stays_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_integration_tool_module(
        tmp_path,
        evaluator=PolicyEvaluator(
            policy=ApprovalPolicy(
                rules=[
                    PolicyRule(
                        action_pattern="post_to_slack",
                        decision=PolicyDecisionType.APPROVAL,
                    ),
                    PolicyRule(action_pattern="*", decision=PolicyDecisionType.AUTO),
                ]
            ),
            storage_path=str(tmp_path / "standing-approvals.json"),
        ),
    )
    monkeypatch.setattr(
        "ds_agent.infrastructure.external.slack_client.SlackClient.send",
        lambda *args, **kwargs: pytest.fail("Slack client should not be called when policy blocks"),
    )
    created = json.loads(
        await ToolRegistry.dispatch(
            "create_work_object",
            {
                "task_contract_id": "TC-2026-001",
                "title": "Policy gated request",
                "request_source": "slack",
                "requestor_id": "U123",
                "requestor_display": "Kim",
                "original_text": "Send the summary back to Slack.",
            },
        )
    )
    work_object_id = created["work_object"]["work_object_id"]

    result = json.loads(
        await ToolRegistry.dispatch(
            "post_to_slack",
            {
                "work_object_id": work_object_id,
                "message": "Sensitive update",
                "webhook_url": "https://example.com/slack",
            },
        )
    )
    assert result["ok"] is True
    assert result["status"] == "pending"
    assert result["error_code"] == "POLICY_APPROVAL_REQUIRED"
    assert result["policy_decision_id"].startswith("PD-")

    fetched = json.loads(
        await ToolRegistry.dispatch("get_work_object", {"work_object_id": work_object_id})
    )
    pending_actions = fetched["work_object"]["metadata"]["pending_policy_actions"]
    assert pending_actions[0]["status"] == "pending"
    assert pending_actions[0]["policy_decision_id"] == result["policy_decision_id"]
    assert fetched["timeline"][-1]["status"] == "pending"
