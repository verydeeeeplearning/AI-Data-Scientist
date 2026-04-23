"""JSON-backed store for resource access policies.

The on-disk shape is one JSON file per workspace, keyed by
``"<resource_type>::<resource_id>"`` so loads and saves stay O(1) without
requiring a query layer. The store is intentionally additive — the
collaboration baseline operates in sole-user mode and only needs to materialise
a policy when an operator explicitly shares a resource.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.domain.access import AccessPolicy
from ds_agent.runtime.transcript_store import get_runtime_storage_root


def _policy_key(resource_type: str, resource_id: str) -> str:
    return f"{resource_type}::{resource_id}"


class JsonAccessPolicyStore:
    """Persist :class:`AccessPolicy` records to a single JSON file."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file_path = root / "access" / "access_policies.json"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def load(
        self,
        *,
        resource_type: str,
        resource_id: str,
    ) -> AccessPolicy | None:
        key = _policy_key(resource_type, resource_id)
        with self._lock:
            policies = self._read_all_unlocked()
        payload = policies.get(key)
        if payload is None:
            return None
        return self._deserialize(payload)

    def save(self, policy: AccessPolicy) -> AccessPolicy:
        key = _policy_key(policy.resource_type, policy.resource_id)
        with self._lock:
            policies = self._read_all_unlocked()
            policies[key] = self._serialize(policy)
            self._write_all_unlocked(policies)
        return policy

    # -- internal helpers -----------------------------------------------------

    def _read_all_unlocked(self) -> dict[str, dict[str, object]]:
        if not self._file_path.exists():
            return {}
        try:
            raw = self._file_path.read_text(encoding="utf-8")
        except OSError:
            return {}
        if not raw.strip():
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        cleaned: dict[str, dict[str, object]] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, dict):
                cleaned[key] = value
        return cleaned

    def _write_all_unlocked(self, policies: dict[str, dict[str, object]]) -> None:
        body = json.dumps(policies, ensure_ascii=False, indent=2, sort_keys=True)
        self._file_path.write_text(body + "\n", encoding="utf-8")

    @staticmethod
    def _serialize(policy: AccessPolicy) -> dict[str, object]:
        return {
            "resource_type": policy.resource_type,
            "resource_id": policy.resource_id,
            "owner_user_id": policy.owner_user_id,
            "viewers": list(policy.viewers),
            "public_link": policy.public_link,
            "public_link_expires_at": policy.public_link_expires_at,
        }

    @staticmethod
    def _deserialize(payload: dict[str, object]) -> AccessPolicy:
        viewers_raw = payload.get("viewers")
        viewers: list[str] = []
        if isinstance(viewers_raw, list):
            viewers = [str(item) for item in viewers_raw if isinstance(item, str)]
        expires = payload.get("public_link_expires_at")
        expires_at = float(expires) if isinstance(expires, (int, float)) else None
        link = payload.get("public_link")
        public_link = link if isinstance(link, str) and link else None
        return AccessPolicy(
            resource_type=str(payload.get("resource_type", "")),
            resource_id=str(payload.get("resource_id", "")),
            owner_user_id=str(payload.get("owner_user_id", "")),
            viewers=viewers,
            public_link=public_link,
            public_link_expires_at=expires_at,
        )
