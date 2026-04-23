"""Startup recovery and orphan reconciliation for persisted runtime state."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.goal import GoalStatus
from ds_agent.domain.entities.messages import ChatMessage
from ds_agent.domain.entities.working_memory import SessionWorkingMemory
from ds_agent.domain.value_objects.analysis_stage import AnalysisStage

_CURRENT_STAGE_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:current stage|stage)\s*:\s*(?P<value>.+?)\s*$"
)
_BLOCKER_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:active blocker|blocker)\s*:\s*(?P<value>.+?)\s*$"
)
_NEXT_STEP_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:next step|suggested next step)\s*:\s*(?P<value>.+?)\s*$"
)
_PENDING_INLINE_PATTERN = re.compile(
    r"(?im)^\s*[-*]\s*(?:pending question|pending questions)\s*:\s*(?P<value>.+?)\s*$"
)
_QUESTION_HINTS = ("please provide", "which ", "what ", "confirm", "clarify")


@dataclass(slots=True)
class RecoveryRecord:
    """One recovery decision made during startup reconciliation."""

    session_id: str
    action: str
    checkpoint_step: int
    pending_approval_count: int = 0
    goal_status: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _CheckpointContinuity:
    current_stage: AnalysisStage | None = None
    blocker: str | None = None
    next_step: str | None = None
    summary_excerpt: str | None = None


class StartupRecovery:
    """Reconcile checkpoints, goals, working memory, and approvals on startup."""

    def __init__(
        self,
        *,
        checkpoint_store: object,
        goal_store: object,
        working_memory_store: object,
        approval_store: object,
        sensor_hub: object | None = None,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._goal_store = goal_store
        self._working_memory_store = working_memory_store
        self._approval_store = approval_store
        self._sensor_hub = sensor_hub

    def recover(self, limit: int = 100) -> list[RecoveryRecord]:
        """Reconcile persisted sessions and optionally enqueue resume events."""
        list_checkpoints = getattr(self._checkpoint_store, "list", None)
        if not callable(list_checkpoints):
            return []
        checkpoints = list(list_checkpoints(limit=limit))
        records: list[RecoveryRecord] = []

        for checkpoint in checkpoints:
            pending_approvals = self._approval_store.list(
                session_id=checkpoint.session_id,
                status=ApprovalStatus.PENDING,
                limit=100,
            )
            active_goal = self._goal_store.get_active_goal(checkpoint.session_id)
            memory = self._working_memory_store.load(checkpoint.session_id)
            checkpoint_continuity = _extract_checkpoint_continuity(checkpoint.messages)
            current_stage = _resolve_stage(memory, checkpoint_continuity)

            pending_questions: list[str] = []
            if memory is not None:
                pending_questions.extend(memory.pending_questions)
            if checkpoint_continuity.blocker:
                pending_questions.append(checkpoint_continuity.blocker)
            pending_questions.extend(approval.question for approval in pending_approvals)
            pending_questions = _dedupe_strings(pending_questions)[:3]

            active_blocker = _first_non_empty(
                pending_questions[0] if pending_questions else None,
                checkpoint_continuity.blocker,
                None if active_goal is None else active_goal.blocked_reason,
            )
            planned_next_step = _first_non_empty(
                None if memory is None else memory.next_step,
                checkpoint_continuity.next_step,
            )
            recovery_note = _build_recovery_note(
                checkpoint_step=checkpoint.step,
                current_stage=current_stage,
                blocker=active_blocker,
            )

            action = "resume_recommended"
            next_step = _build_resume_next_step(planned_next_step)
            goal_status = None if active_goal is None else active_goal.status
            notes = [recovery_note]
            if current_stage is not None:
                notes.append(f"Recovered stage: {current_stage.value}.")
            if planned_next_step:
                notes.append(f"Recovered next step: {planned_next_step}")

            if pending_approvals:
                action = "awaiting_approval"
                next_step = _build_blocked_next_step(planned_next_step)
                notes.append(f"Recovered {len(pending_approvals)} pending approval(s).")
                if active_goal is not None:
                    self._goal_store.mark_status(
                        checkpoint.session_id,
                        active_goal.goal_id,
                        GoalStatus.BLOCKED,
                        run_id=active_goal.last_run_id,
                        note="Recovered pending approval after restart.",
                        blocked_reason=active_blocker,
                    )
                    goal_status = GoalStatus.BLOCKED
            else:
                if active_goal is not None and active_goal.status not in {
                    GoalStatus.COMPLETED,
                    GoalStatus.CANCELLED,
                }:
                    self._goal_store.mark_status(
                        checkpoint.session_id,
                        active_goal.goal_id,
                        GoalStatus.IN_PROGRESS,
                        run_id=active_goal.last_run_id,
                        note="Recovered after restart from persisted checkpoint.",
                    )
                    goal_status = GoalStatus.IN_PROGRESS
                self._publish_resume_event(checkpoint.session_id, checkpoint.step)

            merged_memory = SessionWorkingMemory(
                session_id=checkpoint.session_id,
                active_goal_id=(
                    memory.active_goal_id
                    if memory is not None
                    else (None if active_goal is None else active_goal.goal_id)
                ),
                last_run_id=(
                    memory.last_run_id
                    if memory is not None
                    else (None if active_goal is None else active_goal.last_run_id)
                ),
                last_user_message=None if memory is None else memory.last_user_message,
                current_summary=_build_recovery_summary(
                    memory=memory,
                    continuity=checkpoint_continuity,
                    current_stage=current_stage,
                    blocker=active_blocker,
                ),
                next_step=next_step,
                pending_questions=pending_questions,
                last_reflection=(
                    memory.last_reflection
                    if memory is not None
                    else "Recovered previous session state."
                ),
                recovery_note=recovery_note,
                current_stage=current_stage,
                stage_entered_at=None if memory is None else memory.stage_entered_at,
                updated_at=time.time(),
            )
            self._working_memory_store.save(merged_memory)

            records.append(
                RecoveryRecord(
                    session_id=checkpoint.session_id,
                    action=action,
                    checkpoint_step=checkpoint.step,
                    pending_approval_count=len(pending_approvals),
                    goal_status=None if goal_status is None else goal_status.value,
                    notes=notes,
                )
            )

        return records

    def _publish_resume_event(self, session_id: str, checkpoint_step: int) -> None:
        if self._sensor_hub is None:
            return
        publish = getattr(self._sensor_hub, "publish", None)
        if not callable(publish):
            return
        publish(
            sensor="startup_recovery",
            kind="recovery.resume",
            session_id=session_id,
            surface="daemon",
            message="Resume previously interrupted session after startup recovery.",
            metadata={"dispatch": True, "checkpointStep": checkpoint_step},
        )


def _resolve_stage(
    memory: SessionWorkingMemory | None,
    continuity: _CheckpointContinuity,
) -> AnalysisStage | None:
    if memory is not None and memory.current_stage is not None:
        return memory.current_stage
    return continuity.current_stage


def _build_resume_next_step(planned_next_step: str | None) -> str:
    return planned_next_step or (
        "Resume from the recovered checkpoint and verify the last incomplete action."
    )


def _build_blocked_next_step(planned_next_step: str | None) -> str:
    if planned_next_step:
        return (
            "Wait for the recovered pending approval before resuming autonomous work. "
            f"Planned next step after approval: {planned_next_step}"
        )
    return "Wait for the recovered pending approval before resuming autonomous work."


def _build_recovery_note(
    *,
    checkpoint_step: int,
    current_stage: AnalysisStage | None,
    blocker: str | None,
) -> str:
    note = (
        f"Recovered after restart from checkpoint step {checkpoint_step} at "
        f"{time.strftime('%H:%M:%S')}."
    )
    if current_stage is not None:
        note = _append_sentence(note, f"Current stage: {current_stage.value}.")
    if blocker:
        note = _append_sentence(note, f"Active blocker: {blocker}.")
    return note


def _build_recovery_summary(
    *,
    memory: SessionWorkingMemory | None,
    continuity: _CheckpointContinuity,
    current_stage: AnalysisStage | None,
    blocker: str | None,
) -> str:
    summary = _first_non_empty(
        None if memory is None else memory.current_summary,
        continuity.summary_excerpt,
        "Recovered interrupted session after restart.",
    )
    if current_stage is not None and current_stage.value not in summary.lower():
        summary = _append_sentence(summary, f"Current stage: {current_stage.value}.")
    if blocker and blocker.lower() not in summary.lower():
        summary = _append_sentence(summary, f"Active blocker: {blocker}.")
    return summary


def _append_sentence(base: str, sentence: str) -> str:
    cleaned_base = " ".join(base.split()).strip()
    cleaned_sentence = " ".join(sentence.split()).strip()
    if not cleaned_base:
        return cleaned_sentence
    if not cleaned_sentence:
        return cleaned_base
    if cleaned_sentence.lower() in cleaned_base.lower():
        return cleaned_base
    separator = "" if cleaned_base.endswith((".", "!", "?")) else "."
    return f"{cleaned_base}{separator} {cleaned_sentence}"


def _extract_checkpoint_continuity(messages: list[ChatMessage]) -> _CheckpointContinuity:
    continuity = _CheckpointContinuity()
    for message in reversed(messages):
        content = (message.content or "").strip()
        if not content:
            continue
        if continuity.current_stage is None:
            continuity.current_stage = _extract_stage(content)
        if not continuity.blocker:
            continuity.blocker = _extract_blocker(content)
        if not continuity.next_step:
            continuity.next_step = _extract_field(content, _NEXT_STEP_PATTERN)
        if not continuity.summary_excerpt:
            continuity.summary_excerpt = _extract_summary_excerpt(content)
        if (
            continuity.current_stage is not None
            and continuity.blocker
            and continuity.next_step
            and continuity.summary_excerpt
        ):
            break
    return continuity


def _extract_stage(text: str) -> AnalysisStage | None:
    extracted = _extract_field(text, _CURRENT_STAGE_PATTERN)
    if extracted is None:
        return None

    normalized = re.sub(r"[^a-z_ ]+", " ", extracted.lower()).replace("_", " ")
    normalized = " ".join(normalized.split())
    for stage in AnalysisStage:
        if normalized == stage.value.replace("_", " "):
            return stage
    return None


def _extract_blocker(text: str) -> str | None:
    direct = _extract_field(text, _BLOCKER_PATTERN)
    if direct:
        return direct

    inline_pending = _extract_field(text, _PENDING_INLINE_PATTERN)
    if inline_pending:
        return inline_pending

    nested_pending = _extract_pending_question(text)
    if nested_pending:
        return nested_pending

    for candidate in reversed(re.findall(r"[^.!?\n]*\?+", text)):
        cleaned = _clean_value(candidate)
        lowered = cleaned.lower()
        if any(token in lowered for token in _QUESTION_HINTS):
            return cleaned
    return None


def _extract_pending_question(text: str) -> str | None:
    capture_nested = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        lowered = stripped.lower()
        if not stripped:
            continue
        if lowered in {"- pending questions:", "* pending questions:"}:
            capture_nested = True
            continue
        if capture_nested:
            match = re.match(r"^[-*]\s+(.+?)\s*$", stripped)
            if match:
                return _clean_value(match.group(1))
            capture_nested = False
    return None


def _extract_field(text: str, pattern: re.Pattern[str]) -> str | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    return _clean_value(matches[-1].group("value"))


def _extract_summary_excerpt(text: str) -> str | None:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped in {"[Conversation Summary]", "[Continuity State]"}:
            continue
        if re.match(
            r"^[-*]\s*(?:current stage|stage|active blocker|blocker|next step|"
            r"suggested next step|pending question|pending questions)\s*:",
            stripped,
            flags=re.IGNORECASE,
        ):
            continue
        lines.append(stripped)
    if not lines:
        return None
    return " ".join(lines)


def _clean_value(value: str) -> str:
    return " ".join(value.split()).strip().strip("-*")


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value is None:
            continue
        cleaned = " ".join(value.split()).strip()
        if cleaned:
            return cleaned
    return None


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join(value.split()).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
