"""Record task-contract gate failures into the governed learning inbox."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.application.ports.task_contract_support import TaskContractFailureSignalRecorder
from ds_agent.domain.interfaces.learning import LearningStore

_OPERATOR_INTERVENTION_WARNING_TYPES: dict[str, str] = {
    "forced_transition": "operator_intervention_forced_transition",
    "patch_override": "operator_intervention_patch_override",
    "assumption_edit": "operator_intervention_assumption_edit",
}
_OPERATOR_INTERVENTION_MESSAGES: dict[str, str] = {
    "forced_transition": (
        "Operator manually forced a task contract state transition."
    ),
    "patch_override": (
        "Operator manually patched core task contract fields outside the normal agent workflow."
    ),
    "assumption_edit": (
        "Operator manually edited or overrode an assumption entry."
    ),
}

_VERIFIER_REVIEW_GATE_WARNING_TYPES = {
    "missing_review_verdict": "review_gate_missing_verdict",
    "latest_verdict_not_auto_verifier": "review_gate_non_auto_verdict",
    "latest_verdict_missing_run_id": "review_gate_missing_run_id",
    "stale_review_verdict": "review_gate_stale_verdict",
}
_VERIFIER_REVIEW_GATE_MESSAGES = {
    "missing_review_verdict": "Review transition blocked because no review verdict exists yet.",
    "latest_verdict_not_auto_verifier": (
        "Review transition blocked because the latest orchestrator verdict was not produced by "
        "auto verifier."
    ),
    "latest_verdict_missing_run_id": (
        "Review transition blocked because the latest auto verifier verdict does not carry a run "
        "id."
    ),
    "stale_review_verdict": (
        "Review transition blocked because the latest auto verifier verdict does not match the "
        "active run."
    ),
}


class LearningTaskContractFailureSignalRecorder(TaskContractFailureSignalRecorder):
    """Persist selected task-contract gate failures as governed learning signals."""

    def __init__(self, store: LearningStore) -> None:
        self._ingestor = HarnessWarningIngestor(store)

    def record_transition_failure(
        self,
        *,
        task_id: str,
        session_id: str | None,
        run_id: str | None,
        transition_to: str | None,
        error_code: str,
        message: str,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        normalized_metadata = dict(metadata or {})
        normalized_transition = str(transition_to or "").strip().lower()
        failure_kind = str(normalized_metadata.get("kind") or "").strip().lower()
        failure_code = str(normalized_metadata.get("failure") or "").strip().lower()
        if normalized_transition != "review":
            return
        if failure_kind != "verifier_review_gate":
            return
        warning_type = _VERIFIER_REVIEW_GATE_WARNING_TYPES.get(failure_code)
        if warning_type is None:
            return

        self._ingestor.ingest(
            {
                "id": _source_ref_for_failure(
                    task_id=task_id,
                    transition_to=normalized_transition,
                    failure_code=failure_code,
                    metadata=normalized_metadata,
                ),
                "type": warning_type,
                "severity": "medium",
                "message": _VERIFIER_REVIEW_GATE_MESSAGES[failure_code],
                "suggestion": (
                    "Regenerate a fresh auto-verifier verdict before retrying the review "
                    "transition."
                ),
                "sourceRef": _source_ref_for_failure(
                    task_id=task_id,
                    transition_to=normalized_transition,
                    failure_code=failure_code,
                    metadata=normalized_metadata,
                ),
                "failureSourceKind": "task_contract_gate",
                "failureSignalType": failure_code,
                "failureSourceRef": task_id,
                "rawPayload": {
                    "taskId": task_id,
                    "sessionId": session_id,
                    "runId": run_id,
                    "transitionTo": normalized_transition,
                    "errorCode": error_code,
                    "kind": failure_kind,
                    "failure": failure_code,
                    "message": message,
                    "metadata": normalized_metadata,
                },
            },
            session_id=session_id,
            run_id=run_id,
            surface="task_contract_gate",
        )

    def record_operator_intervention(
        self,
        *,
        task_id: str,
        session_id: str | None,
        run_id: str | None,
        intervention_kind: str,
        reason: str | None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        normalized_metadata = dict(metadata or {})
        normalized_kind = str(intervention_kind or "").strip().lower()
        warning_type = _OPERATOR_INTERVENTION_WARNING_TYPES.get(
            normalized_kind,
            "operator_intervention_unknown",
        )
        default_message = _OPERATOR_INTERVENTION_MESSAGES.get(
            normalized_kind,
            "Operator manually intervened in a task contract operation.",
        )
        normalized_reason = _normalize_text(reason)
        message = (
            f"{default_message} Reason: {normalized_reason}"
            if normalized_reason
            else default_message
        )
        source_ref = _source_ref_for_intervention(
            task_id=task_id,
            intervention_kind=normalized_kind,
            reason=normalized_reason,
            metadata=normalized_metadata,
        )
        self._ingestor.ingest(
            {
                "id": source_ref,
                "type": warning_type,
                "severity": "medium",
                "message": message,
                "suggestion": (
                    "Review recurring operator interventions to identify systematic issues "
                    "that should be encoded in task contract policy."
                ),
                "sourceRef": source_ref,
                "failureSourceKind": "operator_intervention",
                "failureSignalType": normalized_kind,
                "failureSourceRef": task_id,
                "rawPayload": {
                    "taskId": task_id,
                    "sessionId": session_id,
                    "runId": run_id,
                    "interventionKind": intervention_kind,
                    "reason": reason,
                    "metadata": normalized_metadata,
                },
            },
            session_id=session_id,
            run_id=run_id,
            surface="operator_intervention",
        )


def _source_ref_for_failure(
    *,
    task_id: str,
    transition_to: str,
    failure_code: str,
    metadata: Mapping[str, Any],
) -> str:
    latest_verdict_id = _normalize_text(metadata.get("latest_verdict_id")) or "none"
    expected_run_id = _normalize_text(metadata.get("expected_run_id")) or "none"
    latest_run_id = _normalize_text(metadata.get("latest_verdict_run_id")) or "none"
    return (
        "task_contract_gate:"
        f"{task_id}:{transition_to}:{failure_code}:{latest_verdict_id}:{expected_run_id}:"
        f"{latest_run_id}"
    )


def _source_ref_for_intervention(
    *,
    task_id: str,
    intervention_kind: str,
    reason: str | None,
    metadata: Mapping[str, Any],
) -> str:
    """Derive a stable, normalised source-ref for dedup / recurrence tracking.

    The ref incorporates the task, the kind of intervention, and a short hash of
    the reason text so that identical reasons collapse into a single recurrence
    entry while distinct reasons each get their own learning item.
    """
    reason_hash = (
        hashlib.sha256(reason.encode("utf-8")).hexdigest()[:12]
        if reason
        else "no_reason"
    )
    return f"operator_intervention:{task_id}:{intervention_kind}:{reason_hash}"


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
