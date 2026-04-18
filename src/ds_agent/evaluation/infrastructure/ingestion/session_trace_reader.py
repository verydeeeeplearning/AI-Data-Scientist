"""Reconstruct EvalRun models from persisted session stores.

File-level mypy relaxation: this reader deserializes heterogeneous
JSON blobs from the session store; full type narrowing would require
TypedDict scaffolding for every record shape. Tracked as a structural
refactor candidate (Epic-A post-release).
"""

# mypy: disable-error-code="assignment,no-untyped-def,no-any-return,attr-defined"

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable

from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.evaluation.domain.entities.eval_run import (
    EvalApprovalDecision,
    EvalArtifact,
    EvalOperatorFeedback,
    EvalRun,
    EvalToolCall,
)
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubricRecord
from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
from ds_agent.evaluation.domain.errors.evaluation_errors import MissingEvalRunError
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

_SUMMARY_SECTION_PATTERNS = {
    "core_finding": re.compile(r"core finding\s*:", re.IGNORECASE),
    "confidence": re.compile(r"confidence\s*:", re.IGNORECASE),
    "limitations": re.compile(r"limitations?\s*:", re.IGNORECASE),
    "recommended_action": re.compile(
        r"(?:recommended action|next action)\s*:",
        re.IGNORECASE,
    ),
}
_METRIC_PAIR_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9_ %/-]{1,40})\s*[:=]\s*(-?\d+(?:\.\d+)?)"
)


class SessionTraceReader:
    """Read the latest persisted run for a session from runtime stores."""

    def __init__(
        self,
        *,
        transcript_store: JsonTranscriptStore,
        approval_store: JsonApprovalStore | None = None,
        checkpoint_store: JsonCheckpointStore | None = None,
        goal_store: JsonGoalStore | None = None,
        runtime_event_log: RuntimeEventLog | None = None,
        organization_store: JsonOrganizationStore | None = None,
        run_registry: RunRegistry | None = None,
        session_registry: RuntimeSessionRegistry | None = None,
        task_ledger: TaskLedger | None = None,
        human_rubric_store: JsonlHumanRubricStore | None = None,
        review_sampling_store: JsonlReviewSamplingStore | None = None,
    ) -> None:
        self._transcript_store = transcript_store
        self._approval_store = approval_store
        self._checkpoint_store = checkpoint_store
        self._goal_store = goal_store
        self._runtime_event_log = runtime_event_log
        self._organization_store = organization_store
        self._run_registry = run_registry
        self._session_registry = session_registry
        self._task_ledger = task_ledger
        self._human_rubric_store = human_rubric_store
        self._review_sampling_store = review_sampling_store

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> SessionTraceReader:
        session_registry = RuntimeSessionRegistry(workspace_dir)
        return cls(
            transcript_store=JsonTranscriptStore(workspace_dir),
            approval_store=JsonApprovalStore(workspace_dir),
            checkpoint_store=JsonCheckpointStore(workspace_dir),
            goal_store=JsonGoalStore(workspace_dir),
            runtime_event_log=RuntimeEventLog(workspace_dir),
            organization_store=JsonOrganizationStore(workspace_dir),
            run_registry=RunRegistry(session_registry, workspace_dir),
            session_registry=session_registry,
            task_ledger=TaskLedger(workspace_dir),
            human_rubric_store=JsonlHumanRubricStore.for_workspace(workspace_dir),
            review_sampling_store=JsonlReviewSamplingStore.for_workspace(workspace_dir),
        )

    def read_session(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        run_id: str | None = None,
    ) -> EvalRun:
        messages = self._transcript_store.load_messages(session_id)
        if not messages:
            raise MissingEvalRunError(f"No transcript found for session {session_id}.")

        turn_messages = _latest_turn(messages)
        user_prompt = turn_messages[0].content or ""
        final_summary = _last_assistant_message(turn_messages)
        summary_sections = _extract_summary_sections(final_summary)
        tool_calls = _extract_tool_calls(turn_messages)
        underlying_metrics = _extract_underlying_metrics(turn_messages)
        checkpoint = self._resolve_checkpoint(session_id=session_id)
        runtime_session = self._resolve_runtime_session(session_id=session_id)
        registry_run = self._resolve_run_state(
            session_id=session_id,
            run_id=run_id,
            runtime_session=runtime_session,
        )
        usage_record = self._resolve_usage_record(session_id=session_id, run_id=run_id)
        resolved_run_id = (
            run_id
            or (None if registry_run is None else registry_run.run_id)
            or (None if usage_record is None else usage_record.run_id)
            or self._resolve_run_id_from_events(session_id=session_id)
            or f"{session_id}-latest"
        )
        task_state = self._resolve_task_state(run_id=resolved_run_id)
        goal = self._resolve_goal(session_id=session_id, run_id=resolved_run_id)
        approvals = self._resolve_approvals(session_id=session_id, run_id=resolved_run_id)
        human_rubric_record = self._resolve_human_rubric(
            session_id=session_id,
            run_id=resolved_run_id,
        )
        review_sampling = self._resolve_review_sampling(
            session_id=session_id,
            run_id=resolved_run_id,
        )
        decision_ready_at = (
            min((item.created_at for item in approvals), default=None)
            or _goal_decision_ready_at(goal)
            or (None if registry_run is None else registry_run.finished_at)
            or (None if usage_record is None else usage_record.recorded_at)
        )
        finished_at = (
            None if registry_run is None else registry_run.finished_at
        ) or self._resolve_finished_at(session_id=session_id, run_id=resolved_run_id) or (
            None if usage_record is None else usage_record.recorded_at
        )
        if finished_at is None:
            finished_at = time.time()
        started_at = self._resolve_started_at(
            session_id=session_id,
            run_id=resolved_run_id,
            registry_run=registry_run,
            finished_at=finished_at,
        )
        feedback = _build_feedback(approvals, human_rubric_record)
        artifacts = list(_tool_result_artifacts(turn_messages))
        if checkpoint is not None:
            artifacts.append(_checkpoint_artifact(checkpoint))
        if goal is not None:
            artifacts.append(_goal_artifact(goal))
        if task_state is not None:
            artifacts.append(_task_state_artifact(task_state))
        if human_rubric_record is not None:
            artifacts.append(_human_rubric_artifact(human_rubric_record))
        if final_summary.strip():
            artifacts.append(
                EvalArtifact(
                    artifact_type="executive_summary",
                    content=final_summary,
                )
            )
        metadata = {
            "source": "persisted_session_trace",
            "taskId": task_id,
            "timingSource": self._resolve_timing_source(
                registry_run=registry_run,
                usage_record=usage_record,
                session_id=session_id,
                run_id=resolved_run_id,
            ),
        }
        goal_brief = {}
        if checkpoint is not None:
            metadata["checkpointStep"] = checkpoint.step
            metadata["checkpointUpdatedAt"] = checkpoint.updated_at
            metadata["checkpointMessageCount"] = len(checkpoint.messages)
        if task_state is not None:
            metadata["taskId"] = task_state.task_id
            metadata["taskStatus"] = task_state.status.value
            metadata["taskFinishedAt"] = task_state.finished_at
        if goal is not None:
            metadata["goalId"] = goal.goal_id
            metadata["goalStatus"] = goal.status.value
            metadata["goalUpdatedAt"] = goal.updated_at
            if goal.blocked_reason:
                metadata["goalBlockedReason"] = goal.blocked_reason
            if goal.completed_at is not None:
                metadata["goalCompletedAt"] = goal.completed_at
            goal_brief.update(
                {
                    "goal_summary": goal.summary,
                    "goal_detail": goal.detail,
                    "goal_status": goal.status.value,
                }
            )
            if goal.blocked_reason:
                goal_brief["blocked_reason"] = goal.blocked_reason
        if registry_run is not None:
            metadata["runtimeStatus"] = registry_run.status.value
            metadata["surface"] = registry_run.surface
        elif runtime_session is not None:
            metadata["surface"] = runtime_session.surface
        if usage_record is not None:
            metadata["model"] = usage_record.model
            metadata["provider"] = usage_record.provider
        if human_rubric_record is not None:
            metadata["humanRubricReviewerId"] = human_rubric_record.rubric.reviewer_id
            metadata["humanRubricDimensions"] = dict(human_rubric_record.rubric.dimensions)
            metadata["humanRubricRecordedAt"] = human_rubric_record.recorded_at
            if human_rubric_record.rubric.comment:
                metadata["humanRubricComment"] = human_rubric_record.rubric.comment
        if review_sampling is not None:
            metadata["reviewSamplingSampled"] = review_sampling.sampled
            metadata["reviewSamplingTargetRate"] = review_sampling.target_rate
            metadata["reviewSamplingBucket"] = review_sampling.bucket
            metadata["reviewSamplingStratum"] = review_sampling.stratum
            metadata["reviewSamplingPolicyVersion"] = review_sampling.policy_version
            metadata["reviewSamplingRecordedAt"] = review_sampling.recorded_at
        if started_at == finished_at:
            metadata["timingUnavailable"] = True
        return EvalRun(
            run_id=resolved_run_id,
            session_id=session_id,
            task_id=task_id or resolved_run_id,
            mode="online",
            user_prompt=user_prompt,
            started_at=started_at,
            finished_at=finished_at,
            decision_ready_at=decision_ready_at or finished_at,
            cost_usd=(
                usage_record.cost_usd
                if usage_record is not None
                else (0.0 if registry_run is None else registry_run.cost_usd)
            ),
            goal_brief=goal_brief,
            metric_choices=tuple(),
            tool_calls=tuple(tool_calls),
            approvals=tuple(
                EvalApprovalDecision(
                    action=_approval_action(approval.question),
                    requested=True,
                    approved=_approval_is_approved(approval.status.value),
                )
                for approval in approvals
            ),
            artifacts=tuple(artifacts),
            underlying_metrics=underlying_metrics,
            final_summary=final_summary,
            summary_sections=summary_sections,
            operator_feedback=feedback,
            human_rubric=(
                None if human_rubric_record is None else human_rubric_record.rubric
            ),
            metadata=metadata,
        )

    def _resolve_usage_record(self, *, session_id: str, run_id: str | None):
        if self._organization_store is None:
            return None
        records = [
            record
            for record in self._organization_store.list_usage_records()
            if record.session_id == session_id and (run_id is None or record.run_id == run_id)
        ]
        if not records:
            return None
        return max(records, key=lambda item: item.recorded_at)

    def _resolve_run_id_from_events(self, *, session_id: str) -> str | None:
        if self._runtime_event_log is None:
            return None
        for event in self._runtime_event_log.list(session_id=session_id, limit=50):
            if event.run_id:
                return event.run_id
        return None

    def _resolve_runtime_session(self, *, session_id: str):
        if self._session_registry is None:
            return None
        return self._session_registry.get(session_id)

    def _resolve_checkpoint(self, *, session_id: str):
        if self._checkpoint_store is None:
            return None
        return self._checkpoint_store.load(session_id)

    def _resolve_run_state(
        self,
        *,
        session_id: str,
        run_id: str | None,
        runtime_session,
    ):
        if self._run_registry is None:
            return None
        if run_id is not None:
            return self._run_registry.get(run_id)
        if runtime_session is not None and runtime_session.last_run_id:
            run = self._run_registry.get(runtime_session.last_run_id)
            if run is not None:
                return run
        return self._run_registry.latest_for_session(session_id)

    def _resolve_task_state(self, *, run_id: str):
        if self._task_ledger is None:
            return None
        return self._task_ledger.get_state_for_run(run_id)

    def _resolve_goal(self, *, session_id: str, run_id: str):
        if self._goal_store is None:
            return None
        goals = self._goal_store.list_goals(session_id)
        exact_matches = [goal for goal in goals if goal.last_run_id == run_id]
        if exact_matches:
            return max(exact_matches, key=lambda item: item.updated_at)
        active = self._goal_store.get_active_goal(session_id)
        if active is not None:
            return active
        if not goals:
            return None
        return max(goals, key=lambda item: item.updated_at)

    def _resolve_finished_at(self, *, session_id: str, run_id: str) -> float | None:
        if self._runtime_event_log is None:
            return None
        for event in self._runtime_event_log.list(session_id=session_id, limit=50):
            if event.run_id == run_id and event.kind in {
                "task.completed",
                "task.failed",
                "task.cancelled",
            }:
                return event.created_at
        return None

    def _resolve_started_at(
        self,
        *,
        session_id: str,
        run_id: str,
        registry_run,
        finished_at: float,
    ) -> float:
        if registry_run is not None:
            return registry_run.started_at
        if self._runtime_event_log is not None:
            for event in self._runtime_event_log.list(session_id=session_id, limit=50):
                if event.run_id == run_id and event.kind == "task.started":
                    return event.created_at
        return finished_at

    def _resolve_timing_source(
        self,
        *,
        registry_run,
        usage_record,
        session_id: str,
        run_id: str,
    ) -> str:
        if registry_run is not None and registry_run.finished_at is not None:
            return "run_registry"
        if self._resolve_finished_at(session_id=session_id, run_id=run_id) is not None:
            return "runtime_event_log"
        if usage_record is not None:
            return "usage_record"
        return "fallback"

    def _resolve_approvals(self, *, session_id: str, run_id: str) -> list:
        if self._approval_store is None:
            return []
        approvals = self._approval_store.list(session_id=session_id, limit=10_000)
        exact_matches = [approval for approval in approvals if approval.run_id == run_id]
        if exact_matches:
            return sorted(exact_matches, key=lambda item: item.created_at)
        return sorted(approvals, key=lambda item: item.created_at)

    def _resolve_human_rubric(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> HumanRubricRecord | None:
        if self._human_rubric_store is None:
            return None
        return self._human_rubric_store.latest(session_id=session_id, run_id=run_id)

    def _resolve_review_sampling(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> ReviewSamplingDecision | None:
        if self._review_sampling_store is None:
            return None
        return self._review_sampling_store.latest(session_id=session_id, run_id=run_id)


def _latest_turn(messages: list[ChatMessage]) -> list[ChatMessage]:
    last_user_index = max(
        (index for index, message in enumerate(messages) if message.role == Role.USER),
        default=0,
    )
    return messages[last_user_index:]


def _last_assistant_message(messages: Iterable[ChatMessage]) -> str:
    for message in reversed(list(messages)):
        if message.role == Role.ASSISTANT and not message.tool_calls:
            return message.content or ""
    return ""


def _extract_tool_calls(messages: list[ChatMessage]) -> list[EvalToolCall]:
    result_by_id = {
        message.tool_call_id: message
        for message in messages
        if message.role == Role.TOOL and message.tool_call_id is not None
    }
    calls: list[EvalToolCall] = []
    for message in messages:
        if message.role != Role.ASSISTANT or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            tool_result = result_by_id.get(tool_call.id)
            calls.append(
                EvalToolCall(
                    name=tool_call.name,
                    arguments=tool_call.arguments,
                    status=(
                        "error"
                        if tool_result is not None and _is_error_payload(tool_result.content or "")
                        else "ok"
                    ),
                )
            )
    return calls


def _extract_underlying_metrics(messages: list[ChatMessage]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for message in messages:
        if message.role != Role.TOOL:
            continue
        content = message.content or ""
        parsed = _try_parse_json(content)
        if isinstance(parsed.get("metrics"), dict):
            for key, value in parsed["metrics"].items():
                if isinstance(value, (int, float)):
                    metrics[str(key)] = float(value)
        for key, value in parsed.items():
            if isinstance(value, (int, float)):
                metrics[str(key)] = float(value)
        if message.name == "evaluate_model":
            for raw_key, raw_value in _METRIC_PAIR_PATTERN.findall(content):
                metrics[_normalize_metric_key(raw_key)] = float(raw_value)
    return metrics


def _tool_result_artifacts(messages: list[ChatMessage]) -> Iterable[EvalArtifact]:
    type_map = {
        "run_eda": "eda_report",
        "data_profiler": "profile_report",
        "train_model": "model_artifact",
        "evaluate_model": "model_artifact",
        "generate_report": "executive_summary",
    }
    for message in messages:
        if message.role != Role.TOOL or not message.name:
            continue
        artifact_type = type_map.get(message.name)
        if artifact_type is None:
            continue
        yield EvalArtifact(
            artifact_type=artifact_type,
            content=message.content or "",
            evidence_refs=(message.name,),
        )


def _extract_summary_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches: list[tuple[str, int, int]] = []
    for section_name, pattern in _SUMMARY_SECTION_PATTERNS.items():
        match = pattern.search(text)
        if match:
            matches.append((section_name, match.start(), match.end()))
    matches.sort(key=lambda item: item[1])
    for index, (section_name, _, value_start) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        sections[section_name] = text[value_start:next_start].strip()
    return sections


def _goal_decision_ready_at(goal) -> float | None:
    if goal is None or goal.status != GoalStatus.COMPLETED:
        return None
    return goal.completed_at


def _build_feedback(
    approvals: list,
    human_rubric_record: HumanRubricRecord | None,
) -> EvalOperatorFeedback:
    if not approvals:
        feedback = EvalOperatorFeedback()
    else:
        approved_final = any(_approval_is_approved(approval.status.value) for approval in approvals)
        follow_ups = sum(1 for approval in approvals if approval.status.value == "pending")
        feedback = EvalOperatorFeedback(
            approved_final=approved_final,
            follow_up_messages=follow_ups,
        )
    if human_rubric_record is None:
        return feedback
    human_score = human_rubric_record.rubric.dimensions.get("operator_satisfaction")
    if human_score is None:
        return feedback
    return feedback.model_copy(update={"human_score": human_score})


def _checkpoint_artifact(checkpoint) -> EvalArtifact:
    last_messages = []
    for message in checkpoint.messages[-3:]:
        content = " ".join((message.content or "").split())
        if content:
            last_messages.append(f"{message.role.value}: {content[:200]}")
    content = "\n".join(
        [
            f"step: {checkpoint.step}",
            f"updated_at: {checkpoint.updated_at}",
            f"message_count: {len(checkpoint.messages)}",
            *last_messages,
        ]
    )
    return EvalArtifact(
        artifact_type="checkpoint_context",
        content=content,
        metadata={
            "step": checkpoint.step,
            "updatedAt": checkpoint.updated_at,
            "messageCount": len(checkpoint.messages),
        },
        evidence_refs=("checkpoint",),
    )


def _goal_artifact(goal) -> EvalArtifact:
    lines = [
        f"summary: {goal.summary}",
        f"status: {goal.status.value}",
    ]
    if goal.detail:
        lines.append(f"detail: {goal.detail}")
    if goal.blocked_reason:
        lines.append(f"blocked_reason: {goal.blocked_reason}")
    if goal.notes:
        lines.extend(f"note: {note}" for note in goal.notes[-3:])
    return EvalArtifact(
        artifact_type="goal_state",
        content="\n".join(lines),
        metadata={
            "goalId": goal.goal_id,
            "status": goal.status.value,
            "updatedAt": goal.updated_at,
            "completedAt": goal.completed_at,
            "blockedReason": goal.blocked_reason,
            "noteCount": len(goal.notes),
        },
        evidence_refs=(goal.goal_id,),
    )


def _task_state_artifact(task_state) -> EvalArtifact:
    content = "\n".join(
        [
            f"task_id: {task_state.task_id}",
            f"status: {task_state.status.value}",
            f"created_at: {task_state.created_at}",
            f"started_at: {task_state.started_at}",
            f"finished_at: {task_state.finished_at}",
            f"error: {task_state.error or ''}",
        ]
    )
    return EvalArtifact(
        artifact_type="task_trace",
        content=content,
        metadata={
            "taskId": task_state.task_id,
            "status": task_state.status.value,
            "createdAt": task_state.created_at,
            "startedAt": task_state.started_at,
            "finishedAt": task_state.finished_at,
            "error": task_state.error,
        },
        evidence_refs=(task_state.task_id,),
    )


def _human_rubric_artifact(record: HumanRubricRecord) -> EvalArtifact:
    lines = [f"reviewer_id: {record.rubric.reviewer_id}"]
    for name, value in sorted(record.rubric.dimensions.items()):
        lines.append(f"{name}: {value:.3f}")
    if record.rubric.comment:
        lines.append(f"comment: {record.rubric.comment}")
    return EvalArtifact(
        artifact_type="human_rubric",
        content="\n".join(lines),
        metadata={
            "reviewerId": record.rubric.reviewer_id,
            "dimensions": dict(record.rubric.dimensions),
            "comment": record.rubric.comment,
            "recordedAt": record.recorded_at,
        },
        evidence_refs=(f"human_rubric:{record.rubric.reviewer_id}",),
    )


def _approval_action(question: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", question.strip().lower()).strip("_")
    return normalized or "approval"


def _approval_is_approved(status: str) -> bool | None:
    if status == "approved":
        return True
    if status == "rejected":
        return False
    return None


def _is_error_payload(content: str) -> bool:
    parsed = _try_parse_json(content)
    if "error" in parsed:
        return True
    return content.startswith("[DENIED]") or content.startswith("Security check failed:")


def _try_parse_json(content: str) -> dict[str, object]:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_metric_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
