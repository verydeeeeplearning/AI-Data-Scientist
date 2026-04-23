"""File-backed approval store for cross-surface user interaction."""

from __future__ import annotations

import asyncio
import builtins
import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.approval import ApprovalRequest, ApprovalStatus
from ds_agent.runtime.channel_identity import telegram_legacy_session_id
from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)

_POLL_INTERVAL_SECONDS = 0.25


class JsonApprovalStore:
    """Persist and resolve approval requests across surfaces."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "approvals"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def create(
        self,
        *,
        session_id: str,
        run_id: str | None,
        surface: str,
        question: str,
        kind: str = "generic",
        metadata: dict[str, object] | None = None,
        options: list[str] | None = None,
        default: str | None = None,
    ) -> ApprovalRequest:
        """Create and persist a new pending approval."""
        now = time.time()
        approval = ApprovalRequest(
            approval_id=uuid.uuid4().hex[:12],
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            question=question.strip(),
            kind=kind.strip() or "generic",
            metadata=dict(metadata or {}),
            options=list(options or []),
            default=default,
            status=ApprovalStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self._save(approval)
        return approval

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """Load one approval by id."""
        path = self._approval_file(approval_id)
        if not path.exists():
            return None
        try:
            with self._lock:
                data = self._load_unlocked(path)
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(data, dict):
            return None
        return self._deserialize(data)

    def list(
        self,
        *,
        session_id: str | None = None,
        status: ApprovalStatus | None = None,
        limit: int = 20,
    ) -> list[ApprovalRequest]:
        """List approvals ordered by most recent update."""
        approvals: list[ApprovalRequest] = []
        exact_matches: list[ApprovalRequest] = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            approval = self._deserialize(data)
            if session_id is not None:
                if approval.session_id == session_id:
                    exact_matches.append(approval)
                    continue
                approvals.append(approval)
                continue
            if status is not None and approval.status != status:
                continue
            approvals.append(approval)
        if session_id is not None:
            scoped = self._filter_approvals(exact_matches, status=status, limit=limit)
            if scoped:
                return scoped
            if exact_matches:
                return []
            legacy_session_id = telegram_legacy_session_id(session_id)
            if legacy_session_id is not None:
                legacy_matches = [
                    approval for approval in approvals if approval.session_id == legacy_session_id
                ]
                return self._filter_approvals(legacy_matches, status=status, limit=limit)
            return []
        approvals.sort(key=lambda item: item.updated_at, reverse=True)
        return approvals[:limit]

    def latest_pending_for_session(self, session_id: str) -> ApprovalRequest | None:
        """Return the most recent pending approval for a session."""
        pending = self.list(session_id=session_id, status=ApprovalStatus.PENDING, limit=1)
        return pending[0] if pending else None

    def resolve(
        self,
        approval_id: str,
        *,
        status: ApprovalStatus,
        response: str | None = None,
        source: str | None = None,
        actor: str | None = None,
    ) -> ApprovalRequest | None:
        """Resolve a pending approval."""
        with self._lock:
            path = self._approval_file(approval_id)
            if not path.exists():
                return None
            try:
                data = self._load_unlocked(path)
            except (json.JSONDecodeError, OSError):
                return None
            if not isinstance(data, dict):
                return None
            current = self._deserialize(data)
            if current is None:
                return None

            now = time.time()
            current.status = status
            current.response = response if response is not None else current.default
            current.source = source
            current.actor = actor
            current.updated_at = now
            current.resolved_at = now
            self._save_unlocked(current)
            return current

    async def wait_for_resolution(
        self,
        approval_id: str,
        *,
        poll_interval_seconds: float = _POLL_INTERVAL_SECONDS,
    ) -> ApprovalRequest:
        """Poll persisted state until an approval is resolved."""
        while True:
            approval = self.get(approval_id)
            if approval is not None and approval.status != ApprovalStatus.PENDING:
                return approval
            await asyncio.sleep(poll_interval_seconds)

    @property
    def pending_count(self) -> int:
        return len(self.list(status=ApprovalStatus.PENDING, limit=10_000))

    def replace(self, approval: ApprovalRequest) -> None:
        """Persist a mutated approval request."""
        self._save(approval)

    def _save(self, approval: ApprovalRequest) -> None:
        with self._lock:
            self._save_unlocked(approval)

    def _save_unlocked(self, approval: ApprovalRequest) -> None:
        payload = self._serialize(approval)
        self._approval_file(approval.approval_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _load_unlocked(path: Path) -> object:
        return json.loads(path.read_text(encoding="utf-8"))

    def _approval_file(self, approval_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", approval_id).strip("._-") or "approval"
        return self._dir / f"{safe_id}.json"

    @staticmethod
    def _serialize(approval: ApprovalRequest) -> dict[str, object]:
        return {
            "approval_id": approval.approval_id,
            "session_id": approval.session_id,
            "run_id": approval.run_id,
            "surface": approval.surface,
            "question": approval.question,
            "kind": approval.kind,
            "metadata": dict(approval.metadata),
            "options": list(approval.options),
            "default": approval.default,
            "status": approval.status.value,
            "response": approval.response,
            "source": approval.source,
            "actor": approval.actor,
            "created_at": approval.created_at,
            "updated_at": approval.updated_at,
            "resolved_at": approval.resolved_at,
        }

    @staticmethod
    def _deserialize(data: dict[str, object]) -> ApprovalRequest:
        metadata_raw = data.get("metadata")
        metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
        options_raw = data.get("options")
        options = options_raw if isinstance(options_raw, list) else []
        created_at = data.get("created_at", 0.0)
        updated_at = data.get("updated_at", 0.0)
        resolved_at = data.get("resolved_at")
        return ApprovalRequest(
            approval_id=str(data.get("approval_id", "")),
            session_id=str(data.get("session_id", "")),
            run_id=str(data["run_id"]) if data.get("run_id") is not None else None,
            surface=str(data.get("surface", "unknown")),
            question=str(data.get("question", "")),
            kind=str(data.get("kind", "generic")),
            metadata=metadata,
            options=[str(item) for item in options if isinstance(item, str)],
            default=str(data["default"]) if data.get("default") is not None else None,
            status=ApprovalStatus(str(data.get("status", ApprovalStatus.PENDING.value))),
            response=str(data["response"]) if data.get("response") is not None else None,
            source=str(data["source"]) if data.get("source") is not None else None,
            actor=str(data["actor"]) if data.get("actor") is not None else None,
            created_at=float(created_at) if isinstance(created_at, (int, float)) else 0.0,
            updated_at=float(updated_at) if isinstance(updated_at, (int, float)) else 0.0,
            resolved_at=float(resolved_at) if isinstance(resolved_at, (int, float)) else None,
        )

    @staticmethod
    def _filter_approvals(
        approvals: builtins.list[ApprovalRequest],
        *,
        status: ApprovalStatus | None,
        limit: int,
    ) -> builtins.list[ApprovalRequest]:
        if status is not None:
            approvals = [approval for approval in approvals if approval.status == status]
        approvals.sort(key=lambda item: item.updated_at, reverse=True)
        return approvals[:limit]
