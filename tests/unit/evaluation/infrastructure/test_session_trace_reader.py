from __future__ import annotations

import asyncio
from unittest.mock import patch

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric, HumanRubricRecord
from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
from ds_agent.evaluation.infrastructure.ingestion.session_trace_reader import SessionTraceReader
from ds_agent.evaluation.infrastructure.persistence.jsonl_human_rubric_store import (
    JsonlHumanRubricStore,
)
from ds_agent.evaluation.infrastructure.persistence.jsonl_review_sampling_store import (
    JsonlReviewSamplingStore,
)
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
from ds_agent.runtime.goal_store import JsonGoalStore
from ds_agent.runtime.organization_store import JsonOrganizationStore
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.runtime_event_log import RuntimeEventLog
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.task_ledger import TaskLedger
from ds_agent.runtime.transcript_store import JsonTranscriptStore


def test_session_trace_reader_reconstructs_latest_turn(tmp_path) -> None:
    session_id = "session-123"
    run_id = "run-123"
    transcript_store = JsonTranscriptStore(workspace_dir=str(tmp_path))
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Old request"),
            ChatMessage(role=Role.ASSISTANT, content="Old answer"),
            ChatMessage(role=Role.USER, content="Find churn drivers and prepare a summary"),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Running evaluation",
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name="build_features",
                        arguments={"target": "churn_30d"},
                    )
                ],
            ),
            ChatMessage(
                role=Role.TOOL,
                name="build_features",
                tool_call_id="tc-1",
                content='{"status":"ok"}',
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Scoring model",
                tool_calls=[
                    ToolCall(
                        id="tc-2",
                        name="evaluate_model",
                        arguments={"metric": "pr_auc"},
                    )
                ],
            ),
            ChatMessage(
                role=Role.TOOL,
                name="evaluate_model",
                tool_call_id="tc-2",
                content='{"metrics":{"pr_auc":0.82,"lift_at_10pct":2.10}}',
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Core finding: churn risk is concentrated in annual-plan downgrades. "
                    "Confidence: medium-high. "
                    "Limitations: only one quarter of labeled events. "
                    "Recommended action: request approval before campaign launch."
                ),
            ),
        ],
    )

    approval_store = JsonApprovalStore(workspace_dir=str(tmp_path))
    created = approval_store.create(
        session_id=session_id,
        run_id=run_id,
        surface="ws",
        question="Launch retention campaign",
    )
    approval_store.resolve(created.approval_id, status=ApprovalStatus.APPROVED)

    organization_store = JsonOrganizationStore(workspace_dir=str(tmp_path))
    organization_store.record_usage(
        actor_id="local-user",
        provider="anthropic",
        cost_usd=1.23,
        model="anthropic/claude-sonnet-4-6",
        session_id=session_id,
        run_id=run_id,
        recorded_at=created.created_at + 120.0,
    )
    runtime_event_log = RuntimeEventLog(workspace_dir=str(tmp_path))
    runtime_event_log.record(
        category="task",
        kind="task.completed",
        severity="success",
        message="Task completed",
        session_id=session_id,
        run_id=run_id,
        created_at=created.created_at + 120.0,
    )

    reader = SessionTraceReader(
        transcript_store=transcript_store,
        approval_store=approval_store,
        runtime_event_log=runtime_event_log,
        organization_store=organization_store,
    )
    run = reader.read_session(session_id=session_id)

    assert run.run_id == run_id
    assert run.user_prompt == "Find churn drivers and prepare a summary"
    assert run.cost_usd == 1.23
    assert run.final_summary.startswith("Core finding:")
    assert run.summary_sections["confidence"] == "medium-high."
    assert len(run.tool_calls) == 2
    assert run.tool_calls[1].name == "evaluate_model"
    assert run.tool_calls[1].status == "ok"
    assert run.underlying_metrics["pr_auc"] == 0.82
    assert run.approvals[0].approved is True
    assert run.metadata["timingUnavailable"] is True


def test_session_trace_reader_uses_persisted_run_registry_for_timing(tmp_path) -> None:
    session_id = "session-789"
    transcript_store = JsonTranscriptStore(workspace_dir=str(tmp_path))
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Investigate premium churn."),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Core finding: premium churn is rising in new cohorts.",
            ),
        ],
    )

    session_registry = RuntimeSessionRegistry(workspace_dir=str(tmp_path))
    run_registry = RunRegistry(session_registry, workspace_dir=str(tmp_path))
    with patch("ds_agent.runtime.run_registry.time.time", return_value=300.0):
        created = run_registry.create(session_id, "ws", "Investigate premium churn.")
    with patch("ds_agent.runtime.run_registry.time.time", return_value=345.0):
        run_registry.mark_succeeded(created.run_id, result="Done.", cost_usd=0.33)

    reader = SessionTraceReader.for_workspace(str(tmp_path))
    run = reader.read_session(session_id=session_id)

    assert run.run_id == created.run_id
    assert run.started_at == 300.0
    assert run.finished_at == 345.0
    assert run.cost_usd == 0.33
    assert run.metadata["timingSource"] == "run_registry"
    assert run.metadata["runtimeStatus"] == "succeeded"
    assert run.metadata["surface"] == "ws"


async def test_session_trace_reader_stitches_checkpoint_goal_and_task_context(tmp_path) -> None:
    session_id = "session-ctx"
    run_id = "run-ctx"
    transcript_store = JsonTranscriptStore(workspace_dir=str(tmp_path))
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Recover the interrupted churn analysis."),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Core finding: recovery context was restored and the next step is clear.",
            ),
        ],
    )

    checkpoint_store = JsonCheckpointStore(workspace_dir=str(tmp_path))
    checkpoint_store.save(
        SessionCheckpoint(
            session_id=session_id,
            step=4,
            messages=[
                ChatMessage(role=Role.USER, content="Resume the run"),
                ChatMessage(role=Role.ASSISTANT, content="Restoring prior state"),
            ],
            updated_at=410.0,
        )
    )

    goal_store = JsonGoalStore(workspace_dir=str(tmp_path))
    goal = goal_store.ensure_from_message(
        session_id,
        "Recover the interrupted churn analysis.",
        run_id=run_id,
    )
    goal_store.mark_status(
        session_id,
        goal.goal_id,
        GoalStatus.BLOCKED,
        run_id=run_id,
        note="Waiting for operator confirmation before relaunch.",
        blocked_reason="Need approval to relaunch the campaign.",
    )

    task_ledger = TaskLedger(workspace_dir=str(tmp_path))
    task = asyncio.create_task(asyncio.sleep(0.01))
    task_state = task_ledger.register(run_id, task)
    await task_ledger.wait_for_run(run_id, timeout_seconds=1.0)

    runtime_event_log = RuntimeEventLog(workspace_dir=str(tmp_path))
    runtime_event_log.record(
        category="task",
        kind="task.started",
        severity="info",
        message="Task started",
        session_id=session_id,
        run_id=run_id,
        created_at=400.0,
    )
    runtime_event_log.record(
        category="task",
        kind="task.completed",
        severity="success",
        message="Task completed",
        session_id=session_id,
        run_id=run_id,
        created_at=460.0,
    )

    reader = SessionTraceReader.for_workspace(str(tmp_path))
    run = reader.read_session(session_id=session_id, run_id=run_id)

    assert run.metadata["checkpointStep"] == 4
    assert run.metadata["goalStatus"] == "blocked"
    assert run.metadata["goalBlockedReason"] == "Need approval to relaunch the campaign."
    assert run.metadata["taskId"] == task_state.task_id
    assert run.metadata["taskStatus"] == "succeeded"
    assert run.goal_brief["goal_summary"].startswith("Recover the interrupted")
    assert "blocked_reason" in run.goal_brief
    artifact_types = run.artifact_types()
    assert "checkpoint_context" in artifact_types
    assert "goal_state" in artifact_types
    assert "task_trace" in artifact_types


def test_session_trace_reader_loads_latest_human_rubric(tmp_path) -> None:
    session_id = "session-human"
    run_id = "run-human"
    transcript_store = JsonTranscriptStore(workspace_dir=str(tmp_path))
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Review premium churn risk."),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Core finding: premium churn is concentrated in the newest cohort. "
                    "Confidence: medium. "
                    "Limitations: no uplift experiment yet. "
                    "Recommended action: launch a focused save offer pilot."
                ),
            ),
        ],
    )
    JsonOrganizationStore(workspace_dir=str(tmp_path)).record_usage(
        actor_id="local-user",
        provider="anthropic",
        cost_usd=0.5,
        model="anthropic/claude-sonnet-4-6",
        session_id=session_id,
        run_id=run_id,
    )
    rubric_store = JsonlHumanRubricStore.for_workspace(str(tmp_path))
    rubric_store.append(
        HumanRubricRecord(
            session_id=session_id,
            run_id=run_id,
            rubric=HumanRubric(
                reviewer_id="reviewer-1",
                dimensions={
                    "operator_satisfaction": 0.9,
                    "scoping_accuracy": 0.4,
                },
                comment="Good operator experience, weaker scope framing.",
            ),
        )
    )

    run = SessionTraceReader.for_workspace(str(tmp_path)).read_session(
        session_id=session_id,
        run_id=run_id,
    )

    assert run.human_rubric is not None
    assert run.human_rubric.reviewer_id == "reviewer-1"
    assert run.operator_feedback.human_score == 0.9
    assert run.metadata["humanRubricReviewerId"] == "reviewer-1"
    assert "human_rubric" in run.artifact_types()


def test_session_trace_reader_loads_review_sampling_metadata(tmp_path) -> None:
    session_id = "session-sampling"
    run_id = "run-sampling"
    transcript_store = JsonTranscriptStore(workspace_dir=str(tmp_path))
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Review premium churn risk."),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Core finding: premium churn is concentrated in the newest cohort. "
                    "Confidence: medium. "
                    "Limitations: no uplift experiment yet. "
                    "Recommended action: launch a focused save offer pilot."
                ),
            ),
        ],
    )
    JsonOrganizationStore(workspace_dir=str(tmp_path)).record_usage(
        actor_id="local-user",
        provider="anthropic",
        cost_usd=0.5,
        model="anthropic/claude-sonnet-4-6",
        session_id=session_id,
        run_id=run_id,
    )
    JsonlReviewSamplingStore.for_workspace(str(tmp_path)).append(
        ReviewSamplingDecision(
            session_id=session_id,
            run_id=run_id,
            task_id="task-1",
            domain="retail",
            surface="ws",
            target_rate=0.2,
            bucket=0.08,
            sampled=True,
            stratum="domain:retail",
        )
    )

    run = SessionTraceReader.for_workspace(str(tmp_path)).read_session(
        session_id=session_id,
        run_id=run_id,
    )

    assert run.metadata["reviewSamplingSampled"] is True
    assert run.metadata["reviewSamplingTargetRate"] == 0.2
    assert run.metadata["reviewSamplingBucket"] == 0.08
    assert run.metadata["reviewSamplingStratum"] == "domain:retail"
