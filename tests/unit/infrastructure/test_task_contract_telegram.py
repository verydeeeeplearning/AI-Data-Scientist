from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.api.workspace_service import WorkspaceService
from ds_agent.application.dtos.task_contract import ReviewVerdictInputDTO, TaskContractDraftDTO
from ds_agent.channels.base import InboundMessage
from ds_agent.config.schema import AgentConfig, DSAgentConfig, GatewayConfig
from ds_agent.domain.entities.certification import AutonomyRunStat
from ds_agent.domain.entities.review_verdict import ConfidenceBand, Issue
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonItem, ShadowComparisonRecord
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.verifier_container import build_verifier_container
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.runtime_event_log import RuntimeEventLog
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore
from ds_agent.runtime.working_memory import JsonWorkingMemoryStore


def _create_contract(
    workspace_dir: str,
    session_id: str = "telegram:chat1",
    *,
    authority: str | None = None,
    audience: str | None = None,
) -> str:
    container = build_task_contract_container(workspace_dir)
    result = container.create.execute(
        TaskContractDraftDTO.model_validate(
            {
                "session_id": session_id,
                "contract_type": "churn_analysis",
                "business_goal": "Reduce churn by one point",
                "goal_brief": {
                    "business_question": "What drives churn?",
                    "ds_problem_statement": "Binary classification",
                    "comparison_baseline": "last quarter",
                    "decision_to_make": "prioritize interventions",
                    "expected_effort": "M",
                },
                "required_deliverables": [
                    {"type": "exec_brief", "audience": "executive", "format": "pptx"}
                ],
                "authority": authority,
                "audience": audience,
            }
        )
    )
    return str(result["task_id"])


def _make_runner(tmp_path):
    from ds_agent.gateway.telegram_runner import TelegramGatewayRunner
    from ds_agent.runtime.action_token import ActionTokenStore
    from ds_agent.runtime.operator_alert_state_store import JsonOperatorAlertStateStore
    from ds_agent.runtime.operator_preferences_store import JsonOperatorPreferencesStore

    runner = TelegramGatewayRunner.__new__(TelegramGatewayRunner)
    runner._plugin = MagicMock()
    runner._plugin.send_text = AsyncMock()
    runner._plugin.send_file = AsyncMock()
    runner._plugin.answer_callback_query = AsyncMock(return_value=True)
    runner._plugin.edit_message_reply_markup = AsyncMock()
    runner._plugin.chunk_text = MagicMock(side_effect=lambda text: [text])
    runner._sessions = MagicMock()
    runner._transcript_store = JsonTranscriptStore(base_dir=tmp_path)
    runner._checkpoint_store = JsonCheckpointStore(base_dir=tmp_path)
    runner._approval_store = JsonApprovalStore(base_dir=tmp_path)
    runner._goal_store = JsonGoalStore(base_dir=tmp_path)
    runner._working_memory_store = JsonWorkingMemoryStore(base_dir=tmp_path)
    runner._policy_store = JsonPolicyStore(base_dir=tmp_path)
    runner._delivery_policy_store = JsonDeliveryPolicyStore(tmp_path)
    runner._runtime_event_log = RuntimeEventLog(base_dir=tmp_path)
    runner._workspace = WorkspaceService(str(tmp_path))
    runner._config_path = tmp_path / "config.yaml"
    runner._runtime_sessions = RuntimeSessionRegistry()
    runner._runs = RunRegistry(runner._runtime_sessions)
    runner._task_ledger = TaskLedger()
    runner._preferences = JsonOperatorPreferencesStore(tmp_path)
    runner._alert_state = JsonOperatorAlertStateStore(base_dir=tmp_path)
    runner._action_tokens = ActionTokenStore()
    runner._delivery_rate_limiter = runner._build_delivery_rate_limiter()
    runner._operator_chats = set()
    runner._delivery_targets = {}
    runner._seen_runtime_event_ids = set()
    runner._config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path)),
        gateway=GatewayConfig(
            autonomous_runtime_enabled=True,
            automation_profile="balanced",
        ),
    )
    return runner


def _record_verdict(workspace_dir: str, task_id: str) -> str:
    contract_container = build_task_contract_container(workspace_dir)
    contract_container.record_review_verdict.execute(
        ReviewVerdictInputDTO(
            task_id=task_id,
            verdict_id="RV-20268001",
            category="orchestrator",
            result="warn",
            reviewer="verifier",
            summary="Need owner sign-off before close.",
            confidence=ConfidenceBand(score=0.65),
            blocking_issues=[Issue(message="Needs owner sign-off", layer="policy", blocking=True)],
            metadata={"judge_mode": "llm"},
        )
    )
    verdict_view = contract_container.get.execute(task_id, include=["review_verdicts"])
    verdict = verdict_view.review_verdicts[0]
    build_verifier_container(workspace_dir).repo.save(verdict)
    return verdict.verdict_id


def _record_shadow_comparison(workspace_dir: str, verdict_id: str, task_id: str) -> str:
    verdict = build_verifier_container(workspace_dir).repo.get(verdict_id)
    assert verdict is not None
    record = ShadowComparisonRecord(
        comparison_id="SC-20268001",
        verdict_id=verdict_id,
        task_id=task_id,
        run_id="run-1",
        session_id="telegram:chat1",
        created_at=verdict.created_at,
        items=[
            ShadowComparisonItem(
                comparison_key="baseline_guard",
                legacy_source="baseline_guard_hook",
                verifier_targets=["baseline_comparison"],
                applicable=True,
                legacy_state="clear",
                verifier_state="triggered",
                note="verifier flagged an issue that the legacy hook missed",
            )
        ],
    )
    build_verifier_container(workspace_dir).shadow_repo.save(record)
    return record.comparison_id


def _seed_certification_stats(workspace_dir: str) -> None:
    store = SqliteCertificationStore.for_workspace(workspace_dir)
    for index in range(10):
        store.record_run_stat(
            AutonomyRunStat(
                mission_name="weekly-kpi-triage",
                mission_version=1,
                run_id=f"run-{index}",
                authority="shadow",
                audience="senior_staff",
                started_at="2026-04-01T00:00:00Z",
                ended_at="2026-04-01T00:10:00Z",
                outcome="success",
                verifier_score=0.90,
                rollback_rehearsal=index == 0,
            )
        )


@pytest.mark.asyncio
async def test_contract_command_summarizes_active_contract(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    task_id = _create_contract(str(tmp_path))
    message = InboundMessage(
        text="/contract",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    assert task_id in sent.text
    assert "Business goal: Reduce churn by one point" in sent.text


@pytest.mark.asyncio
async def test_contract_agree_command_transitions_contract(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    task_id = _create_contract(str(tmp_path))
    message = InboundMessage(
        text="/contract agree",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    container = build_task_contract_container(str(tmp_path))
    view = container.get.execute(task_id, include=["goal_brief"])
    sent = runner._plugin.send_text.call_args[0][0]
    assert view.contract.status.value == "agreed"
    assert "Transitioned to agreed." in sent.text


@pytest.mark.asyncio
async def test_contract_abandon_command_transitions_contract(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    task_id = _create_contract(str(tmp_path))
    message = InboundMessage(
        text="/contract abandon",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    container = build_task_contract_container(str(tmp_path))
    view = container.get.execute(task_id, include=["goal_brief"])
    sent = runner._plugin.send_text.call_args[0][0]
    assert view.contract.status.value == "abandoned"
    assert "Transitioned to abandoned." in sent.text


@pytest.mark.asyncio
async def test_contract_summary_surfaces_delegate_autonomy(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    _create_contract(str(tmp_path), authority="delegate", audience="senior_staff")
    message = InboundMessage(
        text="/contract",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    assert "authority=delegate" in sent.text
    assert "audience=senior_staff" in sent.text


@pytest.mark.asyncio
async def test_verdict_command_renders_latest_active_verdict(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    task_id = _create_contract(str(tmp_path))
    _record_verdict(str(tmp_path), task_id)
    message = InboundMessage(
        text="/verdict",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    assert "Review verdict: RV-20268001" in sent.text
    assert "judge=llm" in sent.text


@pytest.mark.asyncio
async def test_verdict_shadow_command_renders_latest_shadow_review(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    task_id = _create_contract(str(tmp_path))
    verdict_id = _record_verdict(str(tmp_path), task_id)
    _record_shadow_comparison(str(tmp_path), verdict_id, task_id)
    message = InboundMessage(
        text="/verdict shadow",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    assert "Shadow comparison: SC-20268001" in sent.text
    assert "baseline_guard" in sent.text


@pytest.mark.asyncio
async def test_certification_command_renders_status(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    _seed_certification_stats(str(tmp_path))
    message = InboundMessage(
        text="/certification weekly-kpi-triage",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    assert "Certification: weekly-kpi-triage v1" in sent.text
    assert "shadow_runs=10" in sent.text


@pytest.mark.asyncio
async def test_certification_submit_command_persists_autopilot_record(tmp_path) -> None:
    runner = _make_runner(tmp_path)
    _seed_certification_stats(str(tmp_path))
    message = InboundMessage(
        text="/certification submit weekly-kpi-triage autopilot owner-park owner-cho",
        sender_id="user1",
        conversation_id="chat1",
        channel_id="telegram",
        account_id="bot1",
    )

    await runner._handle_command(message)

    sent = runner._plugin.send_text.call_args[0][0]
    store = SqliteCertificationStore.for_workspace(str(tmp_path))
    assert "Status: certified" in sent.text
    assert store.is_certified("weekly-kpi-triage", "autopilot", mission_version=1) is True
