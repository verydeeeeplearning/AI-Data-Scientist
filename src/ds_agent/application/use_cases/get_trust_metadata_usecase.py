"""Use case for projecting trust metadata from existing backend stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any, Literal

from ds_agent.application.dto.trust_metadata_dto import (
    BadgeStatus,
    TrustApprovalDTO,
    TrustCertificationDTO,
    TrustConfidenceDTO,
    TrustDataWindowDTO,
    TrustDriftDTO,
    TrustFallbackDTO,
    TrustLineageDTO,
    TrustMetadataDTO,
    TrustModelDTO,
    TrustSandboxDTO,
    TrustVerifierDTO,
)
from ds_agent.application.ports.trust_metadata_support import (
    ApprovalLookupPort,
    CertificationLookupPort,
    DeployMonitorLookupPort,
    LineageLookupPort,
    RuntimeEventLookupPort,
    VerdictLookupPort,
)
from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.domain.entities.certification import CertificationRecord
from ds_agent.domain.entities.lineage import LineageRecord
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.runtime.runtime_event_log import RuntimeEventRecord


@dataclass(frozen=True, slots=True)
class _TrustStores:
    verdicts: VerdictLookupPort
    lineage: LineageLookupPort
    certifications: CertificationLookupPort
    approvals: ApprovalLookupPort
    drift: DeployMonitorLookupPort
    events: RuntimeEventLookupPort


_TRUST_EVENT_SUMMARY_MAX_LENGTH = 160


class GetTrustMetadataUseCase:
    """Project verifier, lineage, fallback, approval, and drift metadata."""

    def __init__(
        self,
        *,
        verdict_repo: VerdictLookupPort,
        lineage_store: LineageLookupPort,
        certification_store: CertificationLookupPort,
        approval_store: ApprovalLookupPort,
        drift_store: DeployMonitorLookupPort,
        event_log: RuntimeEventLookupPort,
    ) -> None:
        self._stores = _TrustStores(
            verdicts=verdict_repo,
            lineage=lineage_store,
            certifications=certification_store,
            approvals=approval_store,
            drift=drift_store,
            events=event_log,
        )

    def execute(self, result_id: str) -> TrustMetadataDTO:
        result_id = result_id.strip()
        if not result_id:
            raise ValueError("result_id must be a non-empty string.")

        verdict = self._resolve_verdict(result_id)
        lineage_records = self._resolve_lineage(result_id)
        certification = self._resolve_certification(result_id)
        approval = self._resolve_approval(result_id)
        drift_state = self._stores.drift.latest(result_id)
        events = self._resolve_events(result_id)

        if (
            verdict is None
            and not lineage_records
            and certification is None
            and approval is None
            and drift_state is None
            and not events
        ):
            raise ValueError(f"Trust metadata not found for '{result_id}'.")

        verifier = _build_verifier(verdict, certification)
        lineage = _build_lineage(lineage_records)
        fallback = _build_fallback(events)
        sandbox = _build_sandbox(events)
        drift = _build_drift(drift_state)
        approval_dto = _build_approval(approval)
        model = _build_model(result_id, verdict, drift_state, fallback)
        certification_dto = _build_certification(certification)
        window = _build_window(verdict, lineage_records, approval, drift_state, events)
        confidence = _build_confidence(
            verdict=verdict,
            lineage=lineage,
            certification=certification_dto,
            fallback=fallback,
            approval=approval_dto,
            drift=drift,
            sandbox=sandbox,
        )

        return TrustMetadataDTO(
            resultId=result_id,
            dataWindow=window,
            model=model,
            verifier=verifier,
            lineage=lineage,
            fallback=fallback,
            approval=approval_dto,
            drift=drift,
            sandbox=sandbox,
            confidence=confidence,
            certification=certification_dto,
        )

    def _resolve_verdict(self, result_id: str) -> ReviewVerdict | None:
        matches = self._stores.verdicts.list_for_task(result_id)
        if matches:
            return matches[0]
        return self._stores.verdicts.get(result_id)

    def _resolve_lineage(self, result_id: str) -> list[LineageRecord]:
        exact = self._stores.lineage.get(result_id)
        if exact is not None:
            return _trace_lineage(self._stores.lineage, result_id)
        session = self._stores.lineage.latest_for_session(result_id)
        if session is not None:
            return _trace_lineage(self._stores.lineage, session.id)
        return []

    def _resolve_certification(self, result_id: str) -> CertificationRecord | None:
        return self._stores.certifications.latest_certification(result_id)

    def _resolve_approval(self, result_id: str) -> ApprovalRequest | None:
        exact_matches = [
            approval
            for approval in self._stores.approvals.list(limit=500)
            if _approval_result_id(approval) == result_id
        ]
        if exact_matches:
            return exact_matches[0]
        exact = self._stores.approvals.get(result_id)
        if exact is not None:
            return exact
        matches = self._stores.approvals.list(session_id=result_id, limit=1)
        return matches[0] if matches else None

    def _resolve_events(self, result_id: str) -> list[RuntimeEventRecord]:
        events = self._stores.events.list(limit=500)
        exact_matches = [
            event
            for event in events
            if _event_result_id(event) == result_id
        ]
        if exact_matches:
            return exact_matches
        return [
            event
            for event in events
            if event.run_id == result_id
            or event.session_id == result_id
        ]


def _build_verifier(
    verdict: ReviewVerdict | None,
    certification: CertificationRecord | None,
) -> TrustVerifierDTO:
    if verdict is None:
        return TrustVerifierDTO(status="none", passed=0, total=0, details=[])

    total = sum(len(layer.checks) for layer in verdict.layers)
    passed = sum(
        1 for layer in verdict.layers for check in layer.checks if check.status == "pass"
    )
    details = [
        layer.summary or f"{layer.layer}={layer.overall or 'pass'}"
        for layer in verdict.layers
        if layer.overall not in {None, "pass"}
    ]
    if not details and verdict.summary:
        details.append(verdict.summary)
    if certification is not None and certification.evidence_ref:
        details.append(f"certification evidence: {certification.evidence_ref}")

    if total == 0:
        status: BadgeStatus = "none"
    elif passed == total:
        status = "green"
    elif passed == 0:
        status = "red"
    else:
        status = "yellow"

    return TrustVerifierDTO(
        status=status,
        passed=passed,
        total=total,
        details=details,
    )


def _build_lineage(records: list[LineageRecord]) -> TrustLineageDTO:
    if not records:
        return TrustLineageDTO(status="incomplete", ancestorCount=0)
    return TrustLineageDTO(status="captured", ancestorCount=max(len(records) - 1, 0))


def _build_fallback(events: list[RuntimeEventRecord]) -> TrustFallbackDTO:
    fallback_events = [event for event in events if _is_fallback_event(event)]
    if not fallback_events:
        return TrustFallbackDTO(occurred=False)

    fallback = fallback_events[0]
    metadata = fallback.metadata
    from_model = _mapping_text(metadata, "from")
    to_model = _mapping_text(metadata, "to")
    return TrustFallbackDTO.model_validate(
        {
            "occurred": True,
            "from": from_model,
            "to": to_model,
            "fallbackId": fallback.event_id or None,
            "eventCount": len(fallback_events),
            "summary": _build_fallback_summary(
                fallback, from_model=from_model, to_model=to_model
            ),
            "status": "warning",
        }
    )


def _build_approval(approval: ApprovalRequest | None) -> TrustApprovalDTO:
    if approval is None:
        return TrustApprovalDTO(required=False)
    approved_by = approval.actor or approval.source or approval.response
    return TrustApprovalDTO.model_validate(
        {
            "required": True,
            "approvalId": approval.approval_id,
            "approvalStatus": approval.status.value,
            "approvedBy": (
                approved_by if approval.status != ApprovalStatus.PENDING else None
            ),
        }
    )


def _build_drift(state: Any) -> TrustDriftDTO:
    if state is None:
        return TrustDriftDTO(status="none")
    return TrustDriftDTO(
        status=_status_from_drift(state.drift.overall_status),
        psi=state.drift.max_psi,
    )


def _build_sandbox(events: list[RuntimeEventRecord]) -> TrustSandboxDTO:
    sandbox_events = [event for event in events if _is_sandbox_event(event)]
    if not sandbox_events:
        return TrustSandboxDTO.model_validate({"violationOccurred": False})

    violation = sandbox_events[0]
    return TrustSandboxDTO.model_validate(
        {
            "violationOccurred": True,
            "eventId": violation.event_id or None,
            "eventCount": len(sandbox_events),
            "summary": _build_sandbox_summary(violation),
        }
    )


def _build_certification(certification: CertificationRecord | None) -> TrustCertificationDTO | None:
    if certification is None:
        return None
    return TrustCertificationDTO(
        id=f"{certification.mission_name}:{certification.mission_version}:{certification.level.value}",
        level=_certification_level_to_badge(certification.level.value),
    )


def _build_model(
    result_id: str,
    verdict: ReviewVerdict | None,
    drift_state: Any,
    fallback: TrustFallbackDTO,
) -> TrustModelDTO:
    candidates = [
        _metadata_string(verdict, "primary_model"),
        _metadata_string(verdict, "model"),
        _metadata_string(verdict, "model_id"),
        result_id if drift_state is not None else None,
        fallback.from_model,
    ]
    primary = next((value for value in candidates if value), "unknown")
    return TrustModelDTO.model_validate(
        {"primary": primary, "fallbackOccurred": fallback.occurred}
    )


def _build_window(
    verdict: ReviewVerdict | None,
    lineage_records: list[LineageRecord],
    approval: ApprovalRequest | None,
    drift_state: Any,
    events: list[RuntimeEventRecord],
) -> TrustDataWindowDTO | None:
    timestamps: list[datetime] = []
    if verdict is not None:
        timestamps.append(verdict.created_at)
    timestamps.extend(_record_timestamp(record) for record in lineage_records)
    if approval is not None:
        timestamps.append(_approval_timestamp(approval))
    if drift_state is not None:
        timestamps.append(drift_state.observed_at)
    timestamps.extend(
        datetime.fromtimestamp(event.created_at, tz=UTC)
        for event in events
    )
    timestamps = [item for item in timestamps if item is not None]
    if not timestamps:
        return None
    start = min(timestamps)
    end = max(timestamps)
    days = max(1, ceil((end - start).total_seconds() / 86400.0) + 1)
    return TrustDataWindowDTO(
        start=start.isoformat(),
        end=end.isoformat(),
        days=days,
    )


def _build_confidence(
    *,
    verdict: ReviewVerdict | None,
    lineage: TrustLineageDTO,
    certification: TrustCertificationDTO | None,
    fallback: TrustFallbackDTO,
    approval: TrustApprovalDTO,
    drift: TrustDriftDTO,
    sandbox: TrustSandboxDTO,
) -> TrustConfidenceDTO:
    assumptions: list[str] = []
    evidence_points = 0

    if verdict is not None:
        evidence_points += 1
    else:
        assumptions.append("verifier result was inferred from the task-level result index")

    if lineage.status == "captured":
        evidence_points += 1
    else:
        assumptions.append("lineage chain is incomplete or unavailable")

    if certification is not None:
        evidence_points += 1
    else:
        assumptions.append("no certification record matched this result")

    if drift.status != "none":
        evidence_points += 1
    else:
        assumptions.append("no drift snapshot matched this result")

    if fallback.occurred:
        assumptions.append("provider fallback was observed in runtime events")
        evidence_points += 1

    if approval.required:
        evidence_points += 1
        if approval.approved_by is None:
            assumptions.append("approval was requested but not yet resolved")
    else:
        assumptions.append("no approval request matched this result")

    if sandbox.violation_occurred:
        assumptions.append("sandbox violations were observed for this result")
        evidence_points += 1

    confidence_level: Literal["high", "medium", "low"]
    if evidence_points >= 5 and not assumptions:
        confidence_level = "high"
    elif evidence_points >= 3:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return TrustConfidenceDTO(level=confidence_level, assumptions=assumptions)


def _status_from_drift(value: str) -> BadgeStatus:
    normalized = value.strip().lower()
    if normalized in {"ok", "stable", "green", "pass"}:
        return "green"
    if normalized in {"warning", "yellow"}:
        return "yellow"
    if normalized in {"danger", "alert", "red", "fail"}:
        return "red"
    return "gray"


def _certification_level_to_badge(
    value: str,
) -> Literal["platinum", "gold", "silver"]:
    normalized = value.strip().lower()
    if normalized == "autopilot":
        return "platinum"
    if normalized == "delegate":
        return "gold"
    return "silver"


def _metadata_string(verdict: ReviewVerdict | None, key: str) -> str | None:
    if verdict is None:
        return None
    value = verdict.metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _record_timestamp(record: LineageRecord) -> datetime:
    return datetime.fromtimestamp(record.timestamp, tz=UTC)


def _approval_timestamp(approval: ApprovalRequest) -> datetime:
    value = approval.resolved_at if approval.resolved_at is not None else approval.updated_at
    return datetime.fromtimestamp(value, tz=UTC)


def _approval_result_id(approval: ApprovalRequest) -> str | None:
    metadata_value = approval.metadata.get("resultId") or approval.metadata.get("result_id")
    if metadata_value is None:
        return None
    value = str(metadata_value).strip()
    return value or None


def _event_result_id(event: RuntimeEventRecord) -> str | None:
    metadata_value = event.metadata.get("resultId") or event.metadata.get("result_id")
    if metadata_value is None:
        return None
    value = str(metadata_value).strip()
    return value or None


def _is_fallback_event(event: RuntimeEventRecord) -> bool:
    return event.kind == "provider.fallback" or event.metadata.get("kind") == "provider.fallback"


def _is_sandbox_event(event: RuntimeEventRecord) -> bool:
    return event.kind == "sandbox.violation" or event.metadata.get("kind") == "sandbox.violation"


def _build_fallback_summary(
    event: RuntimeEventRecord,
    *,
    from_model: str | None,
    to_model: str | None,
) -> str:
    reason = _mapping_text(event.metadata, "reason")
    if from_model and to_model:
        base = f"{from_model} -> {to_model}"
        if reason:
            base = f"{base} ({reason.replace('_', ' ')})"
        return _bounded_summary(base) or "provider fallback observed"

    message = _bounded_summary(event.message)
    if message is not None:
        return message

    if reason is not None:
        return (
            _bounded_summary(f"provider fallback ({reason.replace('_', ' ')})")
            or "provider fallback observed"
        )

    return "provider fallback observed"


def _build_sandbox_summary(event: RuntimeEventRecord) -> str:
    detail = _mapping_text(event.metadata, "detail")
    tool = _mapping_text(event.metadata, "tool")
    if detail and tool:
        return _bounded_summary(f"{tool}: {detail}") or "sandbox violation observed"
    if detail:
        return _bounded_summary(detail) or "sandbox violation observed"

    message = _bounded_summary(event.message)
    if message is not None:
        if tool and tool.lower() not in message.lower():
            return _bounded_summary(f"{tool}: {message}") or message
        return message

    if tool is not None:
        return _bounded_summary(f"{tool}: sandbox violation") or "sandbox violation observed"

    return "sandbox violation observed"


def _mapping_text(values: dict[str, object], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bounded_summary(
    value: str,
    *,
    max_length: int = _TRUST_EVENT_SUMMARY_MAX_LENGTH,
) -> str | None:
    text = value.strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _trace_lineage(store: LineageLookupPort, record_id: str) -> list[LineageRecord]:
    chain: list[LineageRecord] = []
    current = store.get(record_id)
    while current is not None:
        chain.append(current)
        if current.parent_id is None:
            break
        current = store.get(current.parent_id)
    chain.reverse()
    return chain
