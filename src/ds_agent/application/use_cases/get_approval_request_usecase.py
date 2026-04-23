"""Load and enrich one persisted approval request for the approval modal."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ds_agent.domain.entities.approval import ApprovalRequest
from ds_agent.domain.security.risk_pattern_descriptions import (
    get_pattern_description,
    merge_affected_scopes,
    recommended_alternative,
    select_primary_pattern_id,
)


class ApprovalStoreLike(Protocol):
    def get(self, approval_id: str) -> ApprovalRequest | None: ...


@dataclass(slots=True)
class ApprovalHighlight:
    """One highlighted code line from the approval explanation."""

    line: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"line": self.line, "reason": self.reason}


@dataclass(slots=True)
class ApprovalPatternMatch:
    """One matched risk pattern and its explanation."""

    pattern_id: str
    description: str
    highlighted_lines: list[ApprovalHighlight] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "patternId": self.pattern_id,
            "description": self.description,
            "highlightedLines": [item.to_dict() for item in self.highlighted_lines],
        }


@dataclass(slots=True)
class ApprovalRequestView:
    """Enriched approval payload returned to the approval modal."""

    approval_id: str
    session_id: str
    run_id: str | None
    surface: str
    question: str
    kind: str
    metadata: dict[str, Any]
    options: list[str]
    default: str | None
    status: str
    response: str | None
    source: str | None
    actor: str | None
    created_at: float
    updated_at: float
    resolved_at: float | None
    workspace_id: str | None = None
    triggered_by: dict[str, Any] | None = None
    risk_code: str = ""
    pattern_matches: list[ApprovalPatternMatch] = field(default_factory=list)
    affected_scopes: list[str] = field(default_factory=list)
    recommended_alternative: str | None = None
    expires_at: float | None = None

    def to_dict(self) -> dict[str, object]:
        payload = {
            "approvalId": self.approval_id,
            "sessionId": self.session_id,
            "runId": self.run_id,
            "surface": self.surface,
            "question": self.question,
            "kind": self.kind,
            "metadata": dict(self.metadata),
            "options": list(self.options),
            "default": self.default,
            "status": self.status,
            "response": self.response,
            "source": self.source,
            "actor": self.actor,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "resolvedAt": self.resolved_at,
            "workspaceId": self.workspace_id,
            "triggeredBy": dict(self.triggered_by) if isinstance(self.triggered_by, dict) else None,
            "riskCode": self.risk_code,
            "patternMatches": [item.to_dict() for item in self.pattern_matches],
            "affectedScopes": list(self.affected_scopes),
            "recommendedAlternative": self.recommended_alternative,
            "expiresAt": self.expires_at,
        }
        return {key: value for key, value in payload.items() if value is not None}


class GetApprovalRequestUseCase:
    """Fetch a persisted approval and attach risk-explanation metadata."""

    def __init__(self, approval_store: ApprovalStoreLike) -> None:
        self._approval_store = approval_store

    def execute(self, approval_id: str | ApprovalRequest) -> ApprovalRequestView:
        approval = self._resolve_approval(approval_id)
        metadata = dict(approval.metadata)
        pattern_matches = self._build_pattern_matches(approval, metadata)
        risk_code = self._resolve_risk_code(approval, metadata, pattern_matches)
        affected_scopes = self._resolve_affected_scopes(metadata, pattern_matches, risk_code)
        recommended = self._resolve_recommended_alternative(
            metadata,
            pattern_matches,
            risk_code,
        )

        return ApprovalRequestView(
            approval_id=approval.approval_id,
            session_id=approval.session_id,
            run_id=approval.run_id,
            surface=approval.surface,
            question=approval.question,
            kind=approval.kind,
            metadata=metadata,
            options=list(approval.options),
            default=approval.default,
            status=approval.status.value,
            response=approval.response,
            source=approval.source,
            actor=approval.actor,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
            resolved_at=approval.resolved_at,
            workspace_id=_first_string(metadata, "workspaceId", "workspace_id"),
            triggered_by=_dict_or_none(metadata, "triggeredBy", "triggered_by"),
            risk_code=risk_code,
            pattern_matches=pattern_matches,
            affected_scopes=affected_scopes,
            recommended_alternative=recommended,
            expires_at=_float_or_none(metadata, "expiresAt", "expires_at"),
        )

    def _resolve_approval(self, approval_id: str | ApprovalRequest) -> ApprovalRequest:
        if isinstance(approval_id, ApprovalRequest):
            return approval_id
        approval = self._approval_store.get(approval_id)
        if approval is None:
            raise ValueError(f"Unknown approvalId: {approval_id}")
        return approval

    def _build_pattern_matches(
        self,
        approval: ApprovalRequest,
        metadata: dict[str, Any],
    ) -> list[ApprovalPatternMatch]:
        raw_matches = metadata.get("patternMatches") or metadata.get("pattern_matches")
        if isinstance(raw_matches, list) and raw_matches:
            return [
                self._build_pattern_match(match, metadata)
                for match in raw_matches
                if isinstance(match, dict)
            ]

        risk_code = _first_string(metadata, "riskCode", "risk_code", "patternId", "pattern_id")
        if not risk_code and approval.kind.startswith("PAT_"):
            risk_code = approval.kind
        if not risk_code:
            return []

        return [self._build_pattern_match({"patternId": risk_code}, metadata)]

    def _build_pattern_match(
        self,
        raw_match: dict[str, Any],
        approval_metadata: dict[str, Any],
    ) -> ApprovalPatternMatch:
        pattern_id = _first_string(
            raw_match,
            "patternId",
            "pattern_id",
            "id",
            default=_first_string(approval_metadata, "riskCode", "risk_code") or "",
        )
        description = self._describe_pattern(pattern_id, approval_metadata)
        highlighted_lines = _normalize_highlights(
            raw_match.get("highlightedLines")
            or raw_match.get("highlighted_lines")
            or raw_match.get("lines")
            or []
        )
        return ApprovalPatternMatch(
            pattern_id=pattern_id,
            description=description,
            highlighted_lines=highlighted_lines,
        )

    def _describe_pattern(
        self,
        pattern_id: str,
        approval_metadata: dict[str, Any],
    ) -> str:
        pattern = get_pattern_description(pattern_id)
        if pattern is not None:
            return pattern["short"]
        fallback = _first_string(approval_metadata, "riskSummary", "risk_summary")
        if fallback:
            return fallback
        return pattern_id

    def _resolve_risk_code(
        self,
        approval: ApprovalRequest,
        metadata: dict[str, Any],
        pattern_matches: list[ApprovalPatternMatch],
    ) -> str:
        risk_code = _first_string(metadata, "riskCode", "risk_code")
        if risk_code:
            return risk_code
        if approval.kind.startswith("PAT_"):
            return approval.kind
        if pattern_matches:
            primary = select_primary_pattern_id(match.pattern_id for match in pattern_matches)
            if primary:
                return primary
            return pattern_matches[0].pattern_id
        return ""

    def _resolve_affected_scopes(
        self,
        metadata: dict[str, Any],
        pattern_matches: list[ApprovalPatternMatch],
        risk_code: str,
    ) -> list[str]:
        raw_scopes = metadata.get("affectedScopes") or metadata.get("affected_scopes")
        if isinstance(raw_scopes, list) and raw_scopes:
            scopes = [str(scope) for scope in raw_scopes if isinstance(scope, str)]
            return _ordered_scopes(scopes)
        candidate_ids = [match.pattern_id for match in pattern_matches]
        if risk_code:
            candidate_ids.append(risk_code)
        return merge_affected_scopes(candidate_ids)

    def _resolve_recommended_alternative(
        self,
        metadata: dict[str, Any],
        pattern_matches: list[ApprovalPatternMatch],
        risk_code: str,
    ) -> str | None:
        explicit = _first_string(
            metadata,
            "recommendedAlternative",
            "recommended_alternative",
            "alternative",
        )
        if explicit:
            return explicit

        candidate_ids = [match.pattern_id for match in pattern_matches]
        if risk_code:
            candidate_ids.append(risk_code)
        return recommended_alternative(candidate_ids)


def _normalize_highlights(raw: Any) -> list[ApprovalHighlight]:
    if not isinstance(raw, list):
        return []

    highlights: list[ApprovalHighlight] = []
    for item in raw:
        if isinstance(item, dict):
            line = item.get("line")
            reason = item.get("reason")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            line, reason = item[0], item[1]
        else:
            continue
        if line is None:
            continue
        try:
            line_number = int(line)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not isinstance(reason, str):
            reason = str(reason)
        highlights.append(ApprovalHighlight(line=line_number, reason=reason))
    return highlights


def _first_string(
    payload: dict[str, Any],
    *keys: str,
    default: str | None = None,
) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return default or ""


def _dict_or_none(payload: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return dict(value)
    return None


def _float_or_none(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _ordered_scopes(scopes: list[str]) -> list[str]:
    order = ("network", "filesystem", "secret", "subprocess")
    values = {scope.strip() for scope in scopes if scope.strip()}
    return [scope for scope in order if scope in values]
