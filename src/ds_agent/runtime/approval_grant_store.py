"""File-backed persistence for approval grants.

Wave 2 W2-F phase 2: stores per-workspace approval grants as one JSON file
per grant under ``runtime/approval_grants/``. Reads stay O(grants) but the
expected steady-state cardinality is small (operator-issued, often revoked
within the same session) so we avoid a full database for now.
"""

from __future__ import annotations

import builtins
import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.approval_grant import (
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalGrantStatus,
)
from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)


class JsonApprovalGrantStore:
    """Persist approval grants on disk and answer scope-specific queries."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "approval_grants"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def issue(
        self,
        *,
        approval_id: str,
        scope: ApprovalGrantScope,
        risk_code: str,
        kind: str,
        session_id: str,
        workspace_id: str | None,
        actor: str | None,
        source: str | None,
        affected_scopes: list[str] | None,
        ttl_seconds: float | None,
        now: float | None = None,
    ) -> ApprovalGrant:
        """Persist one new grant and return it."""

        clock = now if now is not None else time.time()
        expires_at = clock + ttl_seconds if ttl_seconds is not None and ttl_seconds > 0 else None
        grant = ApprovalGrant(
            grant_id=uuid.uuid4().hex[:12],
            approval_id=approval_id,
            scope=scope,
            risk_code=risk_code.strip() or "GENERIC",
            kind=kind.strip() or "generic",
            session_id=session_id,
            workspace_id=workspace_id,
            actor=actor,
            source=source,
            affected_scopes=list(affected_scopes or []),
            created_at=clock,
            expires_at=expires_at,
        )
        self._write(grant)
        return grant

    def get(self, grant_id: str) -> ApprovalGrant | None:
        path = self._grant_file(grant_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        return self._deserialize(payload)

    def list(
        self,
        *,
        session_id: str | None = None,
        workspace_id: str | None = None,
        include_inactive: bool = False,
        now: float | None = None,
    ) -> builtins.list[ApprovalGrant]:
        clock = now if now is not None else time.time()
        results: list[ApprovalGrant] = []
        for path in sorted(self._dir.glob("*.json"), key=lambda entry: entry.name):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            grant = self._deserialize(payload)
            if session_id is not None and grant.session_id != session_id:
                continue
            if workspace_id is not None and grant.workspace_id != workspace_id:
                continue
            if not include_inactive and grant.status(now=clock) != ApprovalGrantStatus.ACTIVE:
                continue
            results.append(grant)
        results.sort(key=lambda item: item.created_at, reverse=True)
        return results

    def find_active_match(
        self,
        *,
        risk_code: str,
        session_id: str,
        workspace_id: str | None,
        now: float | None = None,
    ) -> ApprovalGrant | None:
        """Return any active grant covering ``risk_code`` for the caller."""

        clock = now if now is not None else time.time()
        normalized_code = risk_code.strip()
        if not normalized_code:
            return None
        for grant in self.list(include_inactive=False, now=clock):
            if grant.risk_code != normalized_code:
                continue
            if grant.scope == ApprovalGrantScope.SESSION and grant.session_id != session_id:
                continue
            if (
                grant.scope == ApprovalGrantScope.WORKSPACE
                and workspace_id is not None
                and grant.workspace_id is not None
                and grant.workspace_id != workspace_id
            ):
                continue
            return grant
        return None

    def revoke(
        self,
        grant_id: str,
        *,
        actor: str | None = None,
        now: float | None = None,
    ) -> ApprovalGrant | None:
        """Mark a grant as revoked. No-op if already revoked."""

        with self._lock:
            grant = self.get(grant_id)
            if grant is None:
                return None
            if grant.revoked_at is not None:
                return grant
            grant.revoked_at = now if now is not None else time.time()
            if actor is not None:
                grant.actor = actor
            self._write_unlocked(grant)
            return grant

    def _write(self, grant: ApprovalGrant) -> None:
        with self._lock:
            self._write_unlocked(grant)

    def _write_unlocked(self, grant: ApprovalGrant) -> None:
        path = self._grant_file(grant.grant_id)
        path.write_text(
            json.dumps(self._serialize(grant), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _grant_file(self, grant_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", grant_id).strip("._-") or "grant"
        return self._dir / f"{safe_id}.json"

    @staticmethod
    def _serialize(grant: ApprovalGrant) -> dict[str, object]:
        return {
            "grant_id": grant.grant_id,
            "approval_id": grant.approval_id,
            "scope": grant.scope.value,
            "risk_code": grant.risk_code,
            "kind": grant.kind,
            "session_id": grant.session_id,
            "workspace_id": grant.workspace_id,
            "actor": grant.actor,
            "source": grant.source,
            "affected_scopes": list(grant.affected_scopes),
            "created_at": grant.created_at,
            "expires_at": grant.expires_at,
            "revoked_at": grant.revoked_at,
        }

    @staticmethod
    def _deserialize(payload: dict[str, object]) -> ApprovalGrant:
        scope_value = str(payload.get("scope", ApprovalGrantScope.SESSION.value))
        scope = ApprovalGrantScope(scope_value) if scope_value in {
            entry.value for entry in ApprovalGrantScope
        } else ApprovalGrantScope.SESSION
        affected = payload.get("affected_scopes")
        if isinstance(affected, list):
            affected_scopes = [str(item) for item in affected if isinstance(item, str)]
        else:
            affected_scopes = []
        return ApprovalGrant(
            grant_id=str(payload.get("grant_id", "")),
            approval_id=str(payload.get("approval_id", "")),
            scope=scope,
            risk_code=str(payload.get("risk_code", "GENERIC")),
            kind=str(payload.get("kind", "generic")),
            session_id=str(payload.get("session_id", "")),
            workspace_id=(
                str(payload["workspace_id"])
                if payload.get("workspace_id") is not None
                else None
            ),
            actor=str(payload["actor"]) if payload.get("actor") is not None else None,
            source=str(payload["source"]) if payload.get("source") is not None else None,
            affected_scopes=affected_scopes,
            created_at=_coerce_float(payload.get("created_at"), default=0.0),
            expires_at=_coerce_optional_float(payload.get("expires_at")),
            revoked_at=_coerce_optional_float(payload.get("revoked_at")),
        )


def _coerce_float(value: object, *, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
