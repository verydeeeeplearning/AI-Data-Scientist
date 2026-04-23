"""Persist one approval decision with scope metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus

ApprovalDecision = Literal["allow", "deny"]
ApprovalScope = Literal["once", "session", "workspace"]

_ALLOWED_SCOPES: tuple[str, ...] = ("once", "session", "workspace")


class ApprovalStoreLike(Protocol):
    def get(self, approval_id: str) -> ApprovalRequest | None: ...

    def resolve(
        self,
        approval_id: str,
        *,
        status: ApprovalStatus,
        response: str | None = None,
        source: str | None = None,
        actor: str | None = None,
    ) -> ApprovalRequest | None: ...

    def replace(self, approval: ApprovalRequest) -> None: ...


@dataclass(slots=True)
class SubmitApprovalRequest:
    """Approval decision submitted by the operator surface."""

    approval_id: str
    decision: ApprovalDecision
    scope: ApprovalScope | None = None
    deny_reason: str | None = None
    allow_fallback: bool = False
    response: str | None = None
    actor: str | None = None
    source: str | None = None


@dataclass(slots=True)
class SubmitApprovalResult:
    """Persisted approval decision returned to callers."""

    approval_id: str
    decision: ApprovalDecision
    scope: ApprovalScope | None
    allow_fallback: bool
    status: str
    response: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    denied_reason: str | None = None
    approval: ApprovalRequest | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "approvalId": self.approval_id,
            "decision": self.decision,
            "scope": self.scope,
            "allowFallback": self.allow_fallback,
            "status": self.status,
            "response": self.response,
            "metadata": dict(self.metadata),
            "denyReason": self.denied_reason,
        }


class SubmitApprovalUseCase:
    """Resolve an approval request and persist grant metadata separately."""

    def __init__(self, approval_store: ApprovalStoreLike) -> None:
        self._approval_store = approval_store

    def execute(
        self,
        request: SubmitApprovalRequest | dict[str, Any],
    ) -> SubmitApprovalResult:
        normalized = self._normalize_request(request)
        approval = self._approval_store.get(normalized.approval_id)
        if approval is None:
            raise ValueError(f"Unknown approvalId: {normalized.approval_id}")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is already resolved: {normalized.approval_id}")

        scope = self._normalize_scope(normalized.scope, normalized.decision)
        response = self._resolve_response(normalized, scope)
        status = (
            ApprovalStatus.APPROVED
            if normalized.decision == "allow"
            else ApprovalStatus.REJECTED
        )

        resolved = self._approval_store.resolve(
            normalized.approval_id,
            status=status,
            response=response,
            source=normalized.source,
            actor=normalized.actor,
        )
        if resolved is None:
            raise ValueError(f"Unknown approvalId: {normalized.approval_id}")

        metadata = dict(resolved.metadata)
        # Keep the persisted approval response reserved for operator-entered text.
        resolved.response = response
        decision_payload = {
            "decision": normalized.decision,
            "scope": scope,
            "allowFallback": normalized.allow_fallback,
            "denyReason": normalized.deny_reason,
            "response": response,
            "source": normalized.source,
            "actor": normalized.actor,
        }
        metadata["approvalDecision"] = {
            key: value for key, value in decision_payload.items() if value is not None
        }
        metadata["decision"] = normalized.decision
        if scope is not None:
            metadata["approvalScope"] = scope
            metadata["scope"] = scope
        if normalized.deny_reason is not None:
            metadata["denyReason"] = normalized.deny_reason
        metadata["allowFallback"] = normalized.allow_fallback
        if normalized.source is not None:
            metadata["source"] = normalized.source
        if normalized.actor is not None:
            metadata["actor"] = normalized.actor

        resolved.metadata = metadata
        self._approval_store.replace(resolved)

        return SubmitApprovalResult(
            approval_id=normalized.approval_id,
            decision=normalized.decision,
            scope=scope,
            allow_fallback=normalized.allow_fallback,
            status=status.value,
            response=response,
            metadata=metadata,
            denied_reason=normalized.deny_reason,
            approval=resolved,
        )

    @staticmethod
    def _normalize_request(
        request: SubmitApprovalRequest | dict[str, Any],
    ) -> SubmitApprovalRequest:
        if isinstance(request, SubmitApprovalRequest):
            return request
        payload = dict(request)
        decision = str(payload.get("decision", "")).strip().lower()
        if decision not in {"allow", "deny"}:
            raise ValueError("decision must be 'allow' or 'deny'")
        approval_id = str(
            payload.get("approval_id")
            or payload.get("approvalId")
            or payload.get("requestId")
            or ""
        ).strip()
        if not approval_id:
            raise ValueError("approvalId is required")
        return SubmitApprovalRequest(
            approval_id=approval_id,
            decision=cast(ApprovalDecision, decision),
            scope=SubmitApprovalUseCase._normalize_scope_name(
                payload.get("scope") or payload.get("approvalScope")
            ),
            deny_reason=_first_string(payload, "deny_reason", "denyReason"),
            allow_fallback=bool(
                payload.get("allow_fallback") or payload.get("allowFallback") or False
            ),
            response=_first_string(payload, "response"),
            actor=_first_string(payload, "actor"),
            source=_first_string(payload, "source"),
        )

    @staticmethod
    def _normalize_scope(
        scope: ApprovalScope | None,
        decision: ApprovalDecision,
    ) -> ApprovalScope | None:
        if decision == "allow" and scope is None:
            return "once"
        if scope is None:
            return None
        normalized = scope.strip().lower()
        if normalized not in _ALLOWED_SCOPES:
            raise ValueError("scope must be one of: once, session, workspace")
        return cast(ApprovalScope, normalized)

    @staticmethod
    def _normalize_scope_name(value: object) -> ApprovalScope | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("scope must be a string")
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in _ALLOWED_SCOPES:
            raise ValueError("scope must be one of: once, session, workspace")
        return cast(ApprovalScope, normalized)

    @staticmethod
    def _resolve_response(
        request: SubmitApprovalRequest,
        scope: ApprovalScope | None,
    ) -> str | None:
        _ = scope
        if request.response is not None:
            return request.response
        if request.decision == "deny" and request.deny_reason is not None:
            return request.deny_reason
        if request.decision == "deny":
            return "deny"
        return None


def _first_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None
