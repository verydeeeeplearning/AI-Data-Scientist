"""WebSocket RPC handler — OpenClaw-style req/res + event streaming.

Protocol:
  Client → Server:  {"type":"req", "id":"<uuid>", "method":"chat.send", "params":{...}}
  Server → Client:  {"type":"res", "id":"<uuid>", "ok":true, "payload":{...}}
  Server → Client:  {"type":"event", "event":"stream.delta", "payload":{...}}
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import structlog
from starlette.websockets import WebSocket

from ds_agent.api.callbacks import WsAgentCallbacks
from ds_agent.api.error_mapping import present_invalid_params_error, present_rpc_exception
from ds_agent.api.routes.config import ALLOWED_CONFIG_PATHS
from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.messages import ensure_message_ids
from ds_agent.domain.entities.runtime_state import (
    RunState,
    RuntimeSession,
    RuntimeStatus,
    TaskState,
)
from ds_agent.domain.interfaces.llm_provider import AgentCallbacks
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.domain.value_objects.connector import QuerySpec
from ds_agent.infrastructure.observability import configure_backend_observability
from ds_agent.runtime.approval_payloads import serialize_approval
from ds_agent.runtime.authority_overlay import (
    effective_authority_mode,
    new_incident_started_at,
    resolve_authority_overlay,
)
from ds_agent.runtime.channel_identity import parse_telegram_session_id
from ds_agent.runtime.learning_governance_scheduler import (
    build_learning_governance_status_payload,
)
from ds_agent.runtime.semantic_proposal_router import resolve_semantic_proposal_approval
from ds_agent.runtime.transcript_store import get_runtime_storage_root

if TYPE_CHECKING:
    from ds_agent.agent.core import DSAgent
    from ds_agent.runtime.action_matrix import ActionMatrix

logger = structlog.get_logger()

_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
_BUILTIN_SKILLS_DIR = _SKILLS_ROOT / "builtin"
_SHARED_SKILLS_DIR = _SKILLS_ROOT / "shared"
_CUSTOM_SKILLS_DIR = _SKILLS_ROOT / "custom"
_DEFAULT_ORG_ACTOR = "local-user"
_DEFAULT_REVIEW_SAMPLE_RATE = 0.20
_SELF_IMPROVE_GOVERNANCE_FLAG = "DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1"
_ACTIVE_CUSTOM_SKILLS_DIR_FLAG = "DS_AGENT_ACTIVE_CUSTOM_SKILLS_DIR"
_TRUTHY_FLAG_VALUES = frozenset({"1", "true", "yes"})
_LEARNING_MUTATION_METHODS = frozenset(
    {"learning.review", "learning.rollback", "learning.finalizePromotion"}
)
_LEARNING_INBOX_METADATA_KEYS = (
    "warningType",
    "severity",
    "surface",
    "sessionId",
    "runId",
    "recurrenceCount",
    "firstSeenAt",
    "lastSeenAt",
    "sessionIds",
    "runIds",
    "surfaces",
    "sourceRef",
    "sourceRefs",
    "failureSourceKind",
    "failureSignalType",
    "failureSourceRef",
    "failureSourceCreatedAt",
    "mismatchKind",
    "failureTaxonomyClass",
    "failureTaxonomyLastGcAt",
    "failureTaxonomyRecurrenceCount",
    "failureTaxonomyPromotionCandidate",
    "failureTaxonomyCandidateId",
    "failureTaxonomyCandidateStatus",
    "failureTaxonomyCandidatePath",
)


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _self_improve_governance_enabled() -> bool:
    return os.environ.get(_SELF_IMPROVE_GOVERNANCE_FLAG, "").strip().lower() in _TRUTHY_FLAG_VALUES


def _feature_flags_payload() -> dict[str, bool]:
    return {
        "selfImproveGovernanceV1": _self_improve_governance_enabled(),
    }


def _active_custom_skills_dir() -> Path:
    override = os.environ.get(_ACTIVE_CUSTOM_SKILLS_DIR_FLAG, "").strip()
    if not override:
        return _CUSTOM_SKILLS_DIR
    return Path(override).expanduser().resolve()


def _project_learning_metadata(
    metadata: object,
    *,
    include_raw_payload: bool = False,
) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    if include_raw_payload:
        return dict(metadata)

    projected: dict[str, Any] = {}
    for key in _LEARNING_INBOX_METADATA_KEYS:
        value = metadata.get(key)
        if value is not None:
            projected[key] = value
    return projected


def _serialize_learning_item_summary(
    item: Any,
    *,
    priority_score: float,
) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "type": item.item_type.value,
        "status": item.status.value,
        "title": item.title,
        "priority_score": priority_score,
        "evidence_count": len(item.evidence),
        "conflict_count": len(item.conflict_refs),
        "scope": item.scope,
        "tags": item.tags,
        "created_at": item.created_at.isoformat(),
        "metadata": _project_learning_metadata(item.metadata),
    }


def _serialize_learning_item_detail(
    item: Any,
    *,
    content_limit: int = 1000,
) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "type": item.item_type.value,
        "status": item.status.value,
        "title": item.title,
        "content": item.content[:content_limit],
        "scope": item.scope,
        "review_count": item.review_count,
        "evidence_count": len(item.evidence),
        "conflict_count": len(item.conflict_refs),
        "tags": item.tags,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "metadata": _project_learning_metadata(item.metadata, include_raw_payload=True),
    }


def _serialize_result_cards(cards: Sequence[object] | None) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    if cards is None:
        return payloads
    for card in cards:
        model_dump = getattr(card, "model_dump", None)
        if not callable(model_dump):
            continue
        payload = model_dump(by_alias=True, mode="json")
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _group_result_cards_by_message(
    cards: Sequence[object] | None,
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for payload in _serialize_result_cards(cards):
        source = payload.get("source")
        if not isinstance(source, dict):
            continue
        message_id = source.get("messageId")
        if not isinstance(message_id, str) or not message_id:
            continue
        grouped.setdefault(message_id, []).append(payload)
    return grouped


def _parse_org_role(value: str):
    from ds_agent.domain.entities.organization import OrgRole

    try:
        return OrgRole(value)
    except ValueError as exc:
        raise ValueError(f"Unknown organization role: {value}") from exc


def _provider_name_from_model(model_name: str) -> str:
    from ds_agent.providers.router import parse_model_string

    provider, _model_id = parse_model_string(model_name)
    return provider


def _regression_alert_dedupe_key(*, mode: str | None, domain: str | None) -> str:
    return f"mode={mode or 'all'}::domain={domain or 'all'}"


def _fetch_remote_skill_markdown(url: str, *, timeout_seconds: float = 10.0) -> str:
    """Fetch markdown content from an HTTP(S) URL with basic safety limits."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported")
    request = Request(
        url,
        headers={"User-Agent": "DS-Agent-SkillImporter/1.0"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read(200_000)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Remote skill must be UTF-8 encoded markdown") from exc


def _serialize_runtime_event_record(event: object) -> dict:
    """Convert one runtime-event record to RPC/event payload format."""
    return {
        "eventId": getattr(event, "event_id", ""),
        "category": getattr(event, "category", "runtime"),
        "kind": getattr(event, "kind", ""),
        "severity": getattr(event, "severity", "info"),
        "message": getattr(event, "message", ""),
        "sessionId": getattr(event, "session_id", None),
        "runId": getattr(event, "run_id", None),
        "surface": getattr(event, "surface", "daemon"),
        "source": getattr(event, "source", "runtime"),
        "metadata": dict(getattr(event, "metadata", {}) or {}),
        "createdAt": getattr(event, "created_at", 0.0),
    }


def _normalize_connector_name(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("name is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(char not in allowed for char in normalized):
        raise ValueError("Connector name may contain only letters, numbers, '_' and '-'")
    return normalized


class _TranscriptStepProvider:
    """Resolve the current transcript step for a session.

    Plan 03 anchors operator-named checkpoints at the same step counter the
    implicit ``JsonCheckpointStore`` already maintains for resume flows. We
    look that up via ``checkpoint_store.load(session_id).step`` and fall back
    to counting persisted transcript messages if no implicit checkpoint exists.
    Both lookups are best-effort: a missing session anchors at step 0 so the
    save still succeeds.
    """

    def __init__(
        self,
        transcript_store: Any,
        checkpoint_store: Any | None = None,
    ) -> None:
        self._store = transcript_store
        self._checkpoint_store = checkpoint_store

    def current_step(self, session_id: str) -> int:
        if self._checkpoint_store is not None:
            ckpt_load = getattr(self._checkpoint_store, "load", None)
            if callable(ckpt_load):
                try:
                    checkpoint = ckpt_load(session_id)
                except Exception:
                    checkpoint = None
                if checkpoint is not None and getattr(checkpoint, "step", None) is not None:
                    try:
                        return int(checkpoint.step)
                    except (TypeError, ValueError):
                        pass

        load_messages = getattr(self._store, "load_messages", None)
        if callable(load_messages):
            try:
                messages = load_messages(session_id)
            except Exception:
                return 0
            if isinstance(messages, list):
                return len(messages)
        return 0


class _ParentRunLookupAdapter:
    """Adapter exposing the run registry as a parent-run lookup port."""

    def __init__(self, app_state: Any) -> None:
        self._state = app_state

    def get(self, run_id: str) -> RunState | None:
        return self._state.get_run(run_id)


class _RunLineageLookupAdapter:
    """Adapter exposing runtime run lookups for lineage queries."""

    def __init__(self, app_state: Any) -> None:
        self._state = app_state

    def get(self, run_id: str) -> RunState | None:
        return self._state.get_run(run_id)

    def list(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[RunState]:
        return self._state.list_runs(session_id=session_id, limit=limit)


class _BranchedRunStarter:
    """Adapter that starts a branched agent run via ``AppState.start_run``."""

    def __init__(self, app_state: Any, callbacks: AgentCallbacks) -> None:
        self._state = app_state
        self._callbacks = callbacks

    async def start_branched_run(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        resume_from_checkpoint: bool,
        model: str | None,
    ) -> RunState:
        return await self._state.start_run(
            session_id=session_id,
            message=message,
            callbacks=self._callbacks,
            model=model,
            resume_from_checkpoint=resume_from_checkpoint,
            branched_from_run_id=parent_run_id,
        )


class _RerunFromStepStarter:
    """Adapter that starts a rerun-from-step agent run via ``AppState.start_run``.

    Threading the ``plan_node_id`` through ``start_run`` records the rerun
    anchor on ``RunState.rerun_from_node_id`` while reusing every other
    branched-run mechanic (parent linkage, session inheritance, surface).
    """

    def __init__(self, app_state: Any, callbacks: AgentCallbacks) -> None:
        self._state = app_state
        self._callbacks = callbacks

    async def start_rerun_from_step(
        self,
        *,
        session_id: str,
        message: str,
        parent_run_id: str,
        plan_node_id: str,
        model: str | None,
    ) -> RunState:
        return await self._state.start_run(
            session_id=session_id,
            message=message,
            callbacks=self._callbacks,
            model=model,
            branched_from_run_id=parent_run_id,
            rerun_from_node_id=plan_node_id,
        )


class WsRpcHandler:
    """Dispatch incoming WsRequest frames to the appropriate method handler.

    Holds a reference to the shared ``AppState`` for access to config, agent
    factory, session manager, etc.
    """

    def __init__(self, state: AppState, websocket: WebSocket) -> None:
        self._state = state
        self._ws = websocket
        self._callbacks = WsAgentCallbacks(
            websocket,
            workspace_dir=str(state.config.agent.workspace_dir),
        )
        self._last_run_id: str | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

    # -- Public entry point -----------------------------------------------------

    async def handle_message(self, data: dict) -> None:
        """Route one incoming JSON frame."""
        msg_type = data.get("type")
        if msg_type != "req":
            await self._send_error(data.get("id", ""), "INVALID_TYPE", "Expected type 'req'")
            return

        req_id = data.get("id", str(uuid.uuid4()))
        method = data.get("method", "")
        params = data.get("params") or {}

        handler = self._METHOD_MAP.get(method)
        if handler is None:
            await self._send_error(req_id, "UNKNOWN_METHOD", f"Unknown method: {method}")
            return
        if method in _LEARNING_MUTATION_METHODS and not _self_improve_governance_enabled():
            await self._send_error(req_id, "UNKNOWN_METHOD", f"Unknown method: {method}")
            return

        try:
            result = await handler(self, params)
            await self._send_ok(req_id, result)
        except ValueError as e:
            # ValueError = bad params from client — safe to surface
            presentation = present_invalid_params_error(str(e))
            await self._send_error(req_id, "INVALID_PARAMS", presentation.message)
        except Exception as e:
            # 3.3 fix: never expose internal details to the client
            logger.error("rpc_error", method=method, error=str(e), exc_info=True)
            presentation = present_rpc_exception(method, e)
            await self._send_error(req_id, "INTERNAL", presentation.message)

    # -- RPC Method Handlers ----------------------------------------------------

    async def _chat_send(self, params: dict) -> dict:
        """Start an agent turn. Streams events back via WsAgentCallbacks."""
        return await self._run_start(params)

    async def _chat_abort(self, params: dict) -> dict:
        """Cancel the currently running agent task."""
        if "runId" not in params and "sessionId" not in params and self._last_run_id is not None:
            params = {**params, "runId": self._last_run_id}
        return await self._run_abort(params)

    async def _chat_history(self, params: dict) -> dict:
        """Return chat history for a session."""
        session_id = params.get("sessionId", "")
        limit = params.get("limit", 50)
        history = self._state.get_session_history(session_id, limit=limit)
        ensure_message_ids(history)
        cards_by_message_id = _group_result_cards_by_message(
            self._state.get_session_result_cards(session_id, limit=max(limit * 4, 100))
        )
        messages: list[dict[str, object]] = []
        for message in history:
            payload: dict[str, object] = {
                "messageId": message.message_id,
                "role": message.role.value,
                "content": message.content,
            }
            message_cards = cards_by_message_id.get(message.message_id or "")
            if message_cards:
                payload["cards"] = message_cards
            messages.append(payload)
        return {"messages": messages}

    async def _config_get(self, _params: dict) -> dict:
        """Return current config."""
        return {
            "config": self._state.config_manager.get_dump(),
            "featureFlags": _feature_flags_payload(),
        }

    # 4.8 fix: Single source of truth — import from routes/config.py
    _ALLOWED_CONFIG_PATHS: ClassVar[frozenset[str]] = ALLOWED_CONFIG_PATHS

    async def _config_set(self, params: dict) -> dict:
        """Update a config field by dotted path (whitelisted paths only).

        Uses ConfigManager which handles validation, persistence scope (3.11),
        and whitelist checks.
        """
        path = params.get("path", "")
        value = params.get("value")
        restart_background_runtime = (
            path in {"agent.workspace_dir", "gateway.automation_profile"}
            and self._state.background_runtime_running
        )
        self._state.set_config(path, value)
        if path == "gateway.autonomous_runtime_enabled":
            if bool(value):
                await self._state.start_background_runtime(force=True)
            else:
                await self._state.stop_background_runtime()
        elif restart_background_runtime:
            await self._state.stop_background_runtime()
            await self._state.start_background_runtime(force=True)
        return {"ok": True}

    async def _status_get(self, _params: dict) -> dict:
        """Return agent status summary."""
        return self._state.get_status()

    async def _usage_summary(self, params: dict) -> dict:
        """Return the current actor's usage dashboard summary."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        session_id = (
            str(params.get("sessionId")).strip() if params.get("sessionId") is not None else None
        )
        return self._state.get_usage_summary(actor_id=actor_id, session_id=session_id)

    async def _org_get(self, params: dict) -> dict:
        """Return the current organization snapshot."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        return self._state.get_org_snapshot(actor_id=actor_id)

    async def _org_update_settings(self, params: dict) -> dict:
        """Update organization settings."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        settings = params.get("settings")
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        return self._state.update_org_settings(actor_id=actor_id, settings=settings)

    async def _org_invite_member(self, params: dict) -> dict:
        """Invite one organization member."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        user_id = str(params.get("userId", "")).strip()
        if not user_id:
            raise ValueError("userId is required")
        role = str(params.get("role", "viewer")).strip().lower()
        display_name = params.get("displayName")
        return self._state.invite_org_member(
            actor_id=actor_id,
            user_id=user_id,
            role=role,
            display_name=str(display_name) if display_name is not None else None,
        )

    async def _org_update_member_role(self, params: dict) -> dict:
        """Update one member role."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        user_id = str(params.get("userId", "")).strip()
        role = str(params.get("role", "")).strip().lower()
        if not user_id:
            raise ValueError("userId is required")
        if not role:
            raise ValueError("role is required")
        return self._state.update_org_member_role(actor_id=actor_id, user_id=user_id, role=role)

    async def _org_audit_log_export(self, params: dict) -> dict:
        """Export audit logs for the requested date range."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        start_date = str(params.get("startDate", "")).strip()
        end_date = str(params.get("endDate", "")).strip()
        fmt = str(params.get("format", "csv")).strip().lower()
        if not start_date:
            raise ValueError("startDate is required")
        if not end_date:
            raise ValueError("endDate is required")
        if fmt not in {"csv", "jsonl"}:
            raise ValueError("format must be 'csv' or 'jsonl'")
        return self._state.export_audit_log(
            actor_id=actor_id,
            start_date=start_date,
            end_date=end_date,
            format=fmt,
        )

    async def _skill_catalog(self, _params: dict) -> dict:
        """Return manageable custom skills for the settings UI."""
        return {"skills": self._state.list_manageable_skills()}

    async def _skill_get(self, params: dict) -> dict:
        """Return one editable custom skill."""
        name = str(params.get("name", "")).strip()
        if not name:
            raise ValueError("name is required")
        skill = self._state.get_custom_skill(name)
        if skill is None:
            raise ValueError(f"Unknown custom skill: {name}")
        return {"skill": skill}

    async def _skill_save(self, params: dict) -> dict:
        """Create or update one custom skill."""
        name = str(params.get("name", "")).strip()
        description = str(params.get("description", "")).strip()
        content = str(params.get("content", "")).strip()
        if not name:
            raise ValueError("name is required")
        if not description:
            raise ValueError("description is required")
        if not content:
            raise ValueError("content is required")
        saved = self._state.save_custom_skill(
            name=name,
            description=description,
            content=content,
            category=str(params.get("category", "custom")),
            tags=params.get("tags"),
            tools=params.get("tools"),
            permissions=params.get("permissions"),
            enabled=bool(params.get("enabled", True)),
            existing_name=(
                str(params.get("existingName")).strip()
                if params.get("existingName") is not None
                else None
            ),
        )
        return {"skill": saved, "skills": self._state.list_manageable_skills()}

    async def _skill_import_markdown(self, params: dict) -> dict:
        """Import one raw markdown skill."""
        raw_markdown = str(params.get("markdown", "")).strip()
        if not raw_markdown:
            raise ValueError("markdown is required")
        skill = self._state.import_custom_skill(raw_markdown)
        return {"skill": skill, "skills": self._state.list_manageable_skills()}

    async def _skill_import_url(self, params: dict) -> dict:
        """Import one markdown skill from a remote URL."""
        url = str(params.get("url", "")).strip()
        if not url:
            raise ValueError("url is required")
        skill = self._state.import_custom_skill_from_url(url)
        return {"skill": skill, "skills": self._state.list_manageable_skills()}

    async def _skill_delete(self, params: dict) -> dict:
        """Delete one custom skill."""
        name = str(params.get("name", "")).strip()
        if not name:
            raise ValueError("name is required")
        deleted = self._state.delete_custom_skill(name)
        return {"deleted": deleted, "skills": self._state.list_manageable_skills()}

    async def _skill_toggle(self, params: dict) -> dict:
        """Toggle one custom skill enabled state."""
        name = str(params.get("name", "")).strip()
        if not name:
            raise ValueError("name is required")
        enabled = bool(params.get("enabled", True))
        skill = self._state.set_skill_enabled(name, enabled)
        return {"skill": skill, "skills": self._state.list_manageable_skills()}

    async def _semantic_lookup_metric(self, params: dict) -> dict:
        """Resolve one metric-like query via semantic memory."""
        query = str(params.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        grain = params.get("grain")
        return {
            "lookup": await asyncio.to_thread(
                self._state.semantic_lookup_metric,
                query,
                grain=grain,
            )
        }

    async def _semantic_get_trust(self, params: dict) -> dict:
        """Return semantic trust metadata for one or more tables."""
        fqtns = params.get("fqtns")
        if not isinstance(fqtns, list) or not fqtns:
            raise ValueError("fqtns must be a non-empty list")
        return {
            "trust": await asyncio.to_thread(
                self._state.semantic_get_trust,
                [str(item) for item in fqtns],
                allow_untrusted=bool(params.get("allowUntrusted", False)),
            )
        }

    async def _semantic_get_verified_query(self, params: dict) -> dict:
        """Return the best verified query candidate for a metric."""
        metric_id = str(params.get("metricId", "")).strip()
        if not metric_id:
            raise ValueError("metricId is required")
        bindings = params.get("bindings")
        binding_map = (
            {str(key): value for key, value in bindings.items()}
            if isinstance(bindings, dict)
            else None
        )
        return {
            "verifiedQuery": await asyncio.to_thread(
                self._state.semantic_get_verified_query,
                metric_id,
                dialect=str(params.get("dialect", "postgres")),
                bindings=binding_map,
            )
        }

    async def _semantic_load_pack(self, params: dict) -> dict:
        """Dry-run or apply one semantic pack."""
        return {
            "loadPack": await asyncio.to_thread(
                self._state.semantic_load_pack,
                pack_dir=(
                    str(params.get("packDir")).strip()
                    if params.get("packDir") is not None
                    else None
                ),
                skill_name=(
                    str(params.get("skillName")).strip()
                    if params.get("skillName") is not None
                    else None
                ),
                dry_run=bool(params.get("dryRun", True)),
                allow_definition_updates=bool(params.get("allowDefinitionUpdates", False)),
            )
        }

    async def _semantic_list_snapshots(self, params: dict) -> dict:
        """Return recent semantic snapshots."""
        limit = int(params.get("limit", 20))
        return {
            "snapshots": await asyncio.to_thread(
                self._state.semantic_list_snapshots,
                limit=limit,
            )
        }

    async def _semantic_restore_snapshot(self, params: dict) -> dict:
        """Restore one semantic snapshot into canonical storage."""
        snapshot_id = str(params.get("snapshotId", "")).strip()
        if not snapshot_id:
            raise ValueError("snapshotId is required")
        return {
            "restoreSnapshot": await asyncio.to_thread(
                self._state.semantic_restore_snapshot,
                snapshot_id=snapshot_id,
            )
        }

    async def _semantic_sync_source(self, params: dict) -> dict:
        """Dry-run or apply one external semantic sync source."""
        source_kind = str(params.get("sourceKind", "")).strip().lower()
        if not source_kind:
            raise ValueError("sourceKind is required")
        return {
            "sync": await asyncio.to_thread(
                self._state.semantic_sync_source,
                source_kind=source_kind,
                connector_name=(
                    str(params.get("connectorName")).strip()
                    if params.get("connectorName") is not None
                    else None
                ),
                endpoint=(
                    str(params.get("endpoint")).strip()
                    if params.get("endpoint") is not None
                    else None
                ),
                token=(
                    str(params.get("token")).strip() if params.get("token") is not None else None
                ),
                token_env=(
                    str(params.get("tokenEnv")).strip()
                    if params.get("tokenEnv") is not None
                    else None
                ),
                source_name=(
                    str(params.get("sourceName")).strip()
                    if params.get("sourceName") is not None
                    else None
                ),
                owner=(
                    str(params.get("owner")).strip() if params.get("owner") is not None else None
                ),
                dry_run=bool(params.get("dryRun", True)),
                overwrite=bool(params.get("overwrite", False)),
                id_namespace=(
                    str(params.get("idNamespace")).strip()
                    if params.get("idNamespace") is not None
                    else None
                ),
                since=(
                    str(params.get("since")).strip() if params.get("since") is not None else None
                ),
                allowed_grades=(
                    [str(item) for item in params.get("allowedGrades", [])]
                    if isinstance(params.get("allowedGrades"), list)
                    else None
                ),
            )
        }

    async def _run_start(self, params: dict) -> dict:
        """Start one tracked agent run and return its runtime identifiers."""
        message = params.get("message", "")
        if not message:
            raise ValueError("message is required")

        model = params.get("model")
        session_id = params.get("sessionId") or str(uuid.uuid4())[:8]
        actor_id = str(params.get("actorId")).strip() if params.get("actorId") is not None else None
        resume_flag = bool(params.get("resumeFromCheckpoint", False))
        self._state.publish_user_input_event(session_id=session_id, surface="ws", message=message)
        run = await self._state.start_run(
            session_id=session_id,
            message=message,
            callbacks=self._callbacks,
            model=model,
            actor_id=actor_id,
            resume_from_checkpoint=resume_flag,
        )
        self._last_run_id = run.run_id
        payload = self._serialize_run(run)
        payload["sessionId"] = session_id
        return payload

    async def _run_wait(self, params: dict) -> dict:
        """Wait for a tracked run to reach a terminal state."""
        run_id = params.get("runId") or self._last_run_id
        if not run_id:
            raise ValueError("runId is required")

        timeout_ms = params.get("timeoutMs")
        run = await self._state.wait_for_run(run_id, timeout_ms=timeout_ms)
        if run is None:
            raise ValueError(f"Unknown runId: {run_id}")
        return self._serialize_run(run)

    async def _run_abort(self, params: dict) -> dict:
        """Abort a running task by run id or session id."""
        session_id = params.get("sessionId")
        run_id = params.get("runId")
        if run_id is None and session_id is None:
            run_id = self._last_run_id

        run = await self._state.abort_run(run_id=run_id, session_id=session_id)
        if run is None:
            return {"ok": False, "reason": "no_running_task"}

        self._last_run_id = run.run_id
        payload = self._serialize_run(run)
        payload["ok"] = True
        return payload

    async def _run_list(self, params: dict) -> dict:
        """List tracked runs with optional session/status filters."""
        session_id = params.get("sessionId")
        status_name = params.get("status")
        limit = int(params.get("limit") or 20)
        status = RuntimeStatus(status_name) if status_name else None
        runs = self._state.list_runs(session_id=session_id, status=status, limit=limit)
        return {"runs": [self._serialize_run(run) for run in runs]}

    # -- Checkpoint / Branch handlers (Plan 03 slice) ---------------------

    async def _checkpoint_save(self, params: dict) -> dict:
        """Save a new operator-named checkpoint for a session."""
        from ds_agent.application.use_cases.save_named_checkpoint_usecase import (
            SaveNamedCheckpointInput,
            SaveNamedCheckpointUseCase,
        )

        session_id = str(params.get("sessionId") or "").strip()
        name = str(params.get("name") or "").strip()
        description_raw = params.get("description")
        description = str(description_raw).strip() if description_raw is not None else None

        use_case = SaveNamedCheckpointUseCase(
            store=self._state.checkpoint_store,
            step_provider=_TranscriptStepProvider(
                self._state.transcript_store,
                self._state.checkpoint_store,
            ),
        )
        record = use_case.execute(
            SaveNamedCheckpointInput(
                session_id=session_id,
                name=name,
                description=description,
            )
        )
        return {
            "checkpoint": {
                "id": record.id,
                "name": record.name,
                "sessionId": record.session_id,
                "createdAt": record.created_at,
                "transcriptStep": record.transcript_step,
                "description": record.description,
            }
        }

    async def _checkpoint_list(self, params: dict) -> dict:
        """List operator-named checkpoints for a session, newest first."""
        session_id = str(params.get("sessionId") or "").strip()
        if not session_id:
            raise ValueError("sessionId is required")
        limit = int(params.get("limit") or 50)
        records = self._state.checkpoint_store.list_named(session_id, limit=limit)
        return {
            "checkpoints": [
                {
                    "id": record.id,
                    "name": record.name,
                    "sessionId": record.session_id,
                    "createdAt": record.created_at,
                    "transcriptStep": record.transcript_step,
                    "description": record.description,
                }
                for record in records
            ]
        }

    async def _run_branch(self, params: dict) -> dict:
        """Branch a tracked agent run from a parent run + optional checkpoint."""
        from ds_agent.application.use_cases.branch_run_usecase import (
            BranchRunInput,
            BranchRunUseCase,
        )

        parent_run_id = str(params.get("parentRunId") or "").strip()
        message = str(params.get("message") or "")
        checkpoint_id_raw = params.get("checkpointId")
        checkpoint_id = str(checkpoint_id_raw).strip() if checkpoint_id_raw is not None else None
        model_raw = params.get("model")
        model = str(model_raw).strip() if model_raw is not None else None
        if model == "":
            model = None

        use_case = BranchRunUseCase(
            parent_lookup=_ParentRunLookupAdapter(self._state),
            checkpoint_lookup=self._state.checkpoint_store,
            starter=_BranchedRunStarter(self._state, self._callbacks),
        )
        branched = await use_case.execute(
            BranchRunInput(
                parent_run_id=parent_run_id,
                message=message,
                checkpoint_id=checkpoint_id,
                model=model,
            )
        )
        self._last_run_id = branched.run.run_id
        payload = self._serialize_run(branched.run)
        payload["sessionId"] = branched.run.session_id
        payload["branchedFromRunId"] = branched.parent_run_id
        return payload

    async def _run_rerun(self, params: dict) -> dict:
        """Rerun a tracked agent run from a specific plan-tree node."""
        from ds_agent.application.use_cases.rerun_from_step_usecase import (
            RerunFromStepInput,
            RerunFromStepUseCase,
        )

        parent_run_id = str(params.get("parentRunId") or "").strip()
        plan_node_id = str(params.get("planNodeId") or "").strip()
        message_raw = params.get("message")
        message_override = str(message_raw).strip() if message_raw is not None else None
        model_raw = params.get("model")
        model = str(model_raw).strip() if model_raw is not None else None
        if model == "":
            model = None

        use_case = RerunFromStepUseCase(
            parent_lookup=_ParentRunLookupAdapter(self._state),
            starter=_RerunFromStepStarter(self._state, self._callbacks),
        )
        result = await use_case.execute(
            RerunFromStepInput(
                parent_run_id=parent_run_id,
                plan_node_id=plan_node_id,
                message_override=message_override,
                model=model,
            )
        )
        self._last_run_id = result.run.run_id
        payload = self._serialize_run(result.run)
        payload["sessionId"] = result.run.session_id
        payload["branchedFromRunId"] = result.parent_run_id
        payload["rerunFromNodeId"] = result.plan_node_id
        return payload

    async def _run_promote(self, params: dict) -> dict:
        """Promote one result card to an audience-tagged artifact."""
        from ds_agent.application.use_cases.promote_to_artifact_usecase import (
            PromoteToArtifactInput,
            PromoteToArtifactUseCase,
        )

        run_id = str(params.get("runId") or "").strip()
        card_id = str(params.get("cardId") or "").strip()
        audience = str(params.get("audience") or "").strip()
        title_raw = params.get("title")
        title = str(title_raw).strip() if title_raw is not None else None

        use_case = PromoteToArtifactUseCase(
            store=self._state.promoted_artifact_store,
        )
        artifact = use_case.execute(
            PromoteToArtifactInput(
                run_id=run_id,
                card_id=card_id,
                audience=audience,
                title=title,
            )
        )
        return {
            "artifact": {
                "artifactId": artifact.artifact_id,
                "runId": artifact.run_id,
                "cardId": artifact.card_id,
                "audience": artifact.audience,
                "title": artifact.title,
                "createdAt": artifact.created_at,
            }
        }

    async def _run_list_promoted(self, params: dict) -> dict:
        """List persisted promoted artifacts for one run, newest first."""
        run_id = str(params.get("runId") or "").strip()
        if not run_id:
            raise ValueError("runId is required")
        card_id_raw = params.get("cardId")
        card_id = str(card_id_raw).strip() if card_id_raw is not None else None
        if card_id == "":
            card_id = None
        limit = int(params.get("limit") or 20)
        records = self._state.promoted_artifact_store.list_promoted_artifacts(
            run_id,
            card_id=card_id,
            limit=limit,
        )
        return {
            "artifacts": [
                {
                    "artifactId": record.artifact_id,
                    "runId": record.run_id,
                    "cardId": record.card_id,
                    "audience": record.audience,
                    "title": record.title,
                    "createdAt": record.created_at,
                }
                for record in records
            ]
        }

    async def _runs_list_lineage(self, params: dict) -> dict:
        """List the connected branch / rerun lineage tree for one run family."""
        from ds_agent.application.use_cases.list_run_lineage_usecase import (
            ListRunLineageUseCase,
        )

        root_run_id = str(params.get("rootRunId") or "").strip()
        use_case = ListRunLineageUseCase(_RunLineageLookupAdapter(self._state))
        result = use_case.execute(root_run_id)
        return {
            "rootRunId": result.root_run_id,
            "seedRunId": result.seed_run_id,
            "nodes": [
                {
                    "runId": node.run.run_id,
                    "sessionId": node.run.session_id,
                    "status": node.run.status.value,
                    "message": node.run.message,
                    "createdAt": node.run.created_at,
                    "startedAt": node.run.started_at,
                    "finishedAt": node.run.finished_at,
                    "branchedFromRunId": node.run.branched_from_run_id,
                    "rerunFromNodeId": node.run.rerun_from_node_id,
                    "depth": node.depth,
                    "isRoot": node.is_root,
                    "isSeed": node.is_seed,
                }
                for node in result.nodes
            ],
        }

    async def _session_list(self, params: dict) -> dict:
        """List runtime-visible sessions."""
        limit = int(params.get("limit") or 20)
        sessions = self._state.list_sessions(limit=limit)
        return {"sessions": [self._serialize_session(session) for session in sessions]}

    async def _task_list(self, params: dict) -> dict:
        """List tracked tasks with optional run/status filters."""
        run_id = params.get("runId")
        status_name = params.get("status")
        limit = int(params.get("limit") or 20)
        status = RuntimeStatus(status_name) if status_name else None
        tasks = self._state.list_tasks(run_id=run_id, status=status, limit=limit)
        return {"tasks": [self._serialize_task(task) for task in tasks]}

    async def _runtime_events_list(self, params: dict) -> dict:
        """List recent operator-visible runtime events."""
        limit = int(params.get("limit") or 50)
        session_id = params.get("sessionId")
        category = params.get("category")
        events = self._state.list_runtime_events(
            limit=limit,
            session_id=session_id,
            category=category,
        )
        return {"events": [_serialize_runtime_event_record(event) for event in events]}

    async def _approval_list(self, params: dict) -> dict:
        """List approval requests with optional session/status filters."""
        session_id = params.get("sessionId")
        status_name = params.get("status")
        limit = int(params.get("limit") or 20)
        status = ApprovalStatus(status_name) if status_name else None
        approvals = self._state.list_approvals(session_id=session_id, status=status, limit=limit)
        return {"approvals": [self._serialize_approval(item) for item in approvals]}

    async def _approval_get(self, params: dict) -> dict:
        """Return one approval request enriched for the approval modal."""
        approval_id = str(params.get("approvalId") or params.get("requestId") or "").strip()
        if not approval_id:
            raise ValueError("approvalId is required")
        approval: Any = self._state.get_approval_request(approval_id)
        return approval.to_dict()

    async def _approval_submit(self, params: dict) -> dict:
        """Submit an approval decision using the v2 approval contract."""
        result: Any = self._state.submit_approval(params)
        if result.approval is not None:
            self._callbacks.emit_event(
                "approval.resolved",
                self._serialize_approval(result.approval),
            )
        return result.to_dict()

    async def _approval_resolve(self, params: dict) -> dict:
        """Resolve one pending approval."""
        approval_id = params.get("approvalId", "").strip()
        decision = params.get("decision", "").strip().lower()
        response = params.get("response")
        actor = params.get("actor")

        if not approval_id:
            raise ValueError("approvalId is required")
        if decision not in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}:
            raise ValueError("decision must be 'approved' or 'rejected'")

        approval = self._state.resolve_approval(
            approval_id,
            status=ApprovalStatus(decision),
            response=response if isinstance(response, str) else None,
            source="ws",
            actor=actor if isinstance(actor, str) else None,
        )
        if approval is None:
            raise ValueError(f"Unknown approvalId: {approval_id}")

        payload = self._serialize_approval(approval)
        self._callbacks.emit_event("approval.resolved", payload)
        return payload

    async def _policy_get(self, _params: dict) -> dict:
        """Return autonomous policy state for operator surfaces."""
        action_matrix = self._state.build_action_matrix()
        default_matrix = action_matrix.default()
        overrides = self._state.get_action_matrix_overrides()
        return {
            "automationProfile": str(self._state.config.gateway.automation_profile),
            "recurringGoals": [
                self._serialize_recurring_goal(goal) for goal in self._state.list_recurring_goals()
            ],
            "standingOrders": self._state.get_standing_orders(),
            "actionMatrixRows": [
                self._serialize_action_matrix_row(
                    action_name,
                    effective_row=action_matrix.matrix[action_name],
                    default_row=default_matrix.matrix.get(
                        action_name,
                        default_matrix.matrix["unknown"],
                    ),
                    override_row=overrides.get(action_name, {}),
                )
                for action_name in action_matrix.matrix
            ],
            "actionMatrixOverrides": overrides,
            "actionMatrixOverrideCount": sum(len(row) for row in overrides.values()),
        }

    async def _policy_upsert_recurring_goal(self, params: dict) -> dict:
        """Create or update one recurring autonomous goal."""
        session_id = str(params.get("sessionId", "")).strip()
        prompt = str(params.get("prompt", "")).strip()
        interval_seconds = params.get("intervalSeconds")
        if not session_id:
            raise ValueError("sessionId is required")
        if not prompt:
            raise ValueError("prompt is required")
        if interval_seconds is None:
            raise ValueError("intervalSeconds is required")

        goal = self._state.upsert_recurring_goal(
            session_id=session_id,
            prompt=prompt,
            interval_seconds=float(interval_seconds),
            enabled=bool(params.get("enabled", True)),
            goal_id=(
                str(params.get("goalId", "")).strip() if params.get("goalId") is not None else None
            ),
        )
        return {"goal": self._serialize_recurring_goal(goal)}

    async def _policy_set_standing_orders(self, params: dict) -> dict:
        """Replace standing automation orders."""
        orders = params.get("orders")
        if not isinstance(orders, list):
            raise ValueError("orders must be a list")
        normalized = [str(item) for item in orders if str(item).strip()]
        self._state.set_standing_orders(normalized)
        return {"standingOrders": self._state.get_standing_orders()}

    async def _decision_os_overview(self, params: dict) -> dict:
        """Return Decision OS overview data for the review surface."""
        return self._state.decision_os_overview(
            run_limit=int(params.get("runLimit") or 20),
            model_limit=int(params.get("modelLimit") or 20),
            decision_limit=int(params.get("decisionLimit") or 20),
        )

    async def _decision_os_compare_runs(self, params: dict) -> dict:
        """Return one structured Decision OS run diff."""
        run_a_id = str(params.get("runAId") or params.get("run_a_id") or "").strip()
        run_b_id = str(params.get("runBId") or params.get("run_b_id") or "").strip()
        if not run_a_id:
            raise ValueError("runAId is required")
        if not run_b_id:
            raise ValueError("runBId is required")
        try:
            return self._state.decision_os_compare_runs(run_a_id=run_a_id, run_b_id=run_b_id)
        except LookupError as exc:
            raise ValueError(str(exc)) from exc

    async def _decision_os_request_promotion(self, params: dict) -> dict:
        """Create one promotion-gate decision from the review surface."""
        candidate_run_id = str(
            params.get("candidateRunId") or params.get("candidate_run_id") or ""
        ).strip()
        target_stage = str(params.get("targetStage") or params.get("target_stage") or "").strip()
        rollback_plan_ref = str(
            params.get("rollbackPlanRef") or params.get("rollback_plan_ref") or ""
        ).strip()
        approvers = params.get("approvers")
        if not candidate_run_id:
            raise ValueError("candidateRunId is required")
        if not target_stage:
            raise ValueError("targetStage is required")
        if not rollback_plan_ref:
            raise ValueError("rollbackPlanRef is required")
        if not isinstance(approvers, list):
            raise ValueError("approvers must be a list")
        try:
            return self._state.decision_os_request_promotion(
                candidate_run_id=candidate_run_id,
                target_stage=target_stage,
                approvers=[str(item) for item in approvers if str(item).strip()],
                rollback_plan_ref=rollback_plan_ref,
            )
        except LookupError as exc:
            raise ValueError(str(exc)) from exc

    async def _decision_os_resolve_promotion(self, params: dict) -> dict:
        """Resolve one Decision OS promotion approval step."""
        decision_id = str(params.get("decisionId") or params.get("decision_id") or "").strip()
        decision = str(params.get("decision") or "").strip().lower()
        approver = str(params.get("approver") or "").strip()
        note = str(params.get("note") or params.get("reason") or "").strip()
        if not decision_id:
            raise ValueError("decisionId is required")
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be 'approved' or 'rejected'")
        if not approver:
            raise ValueError("approver is required")
        try:
            return self._state.decision_os_resolve_promotion(
                decision_id=decision_id,
                decision=decision,
                approver=approver,
                note=note,
            )
        except LookupError as exc:
            raise ValueError(str(exc)) from exc

    async def _decision_os_apply_promotion(self, params: dict) -> dict:
        """Apply one approved Decision OS promotion to the model registry."""
        decision_id = str(params.get("decisionId") or params.get("decision_id") or "").strip()
        if not decision_id:
            raise ValueError("decisionId is required")
        try:
            return self._state.decision_os_apply_promotion(decision_id=decision_id)
        except LookupError as exc:
            raise ValueError(str(exc)) from exc

    async def _decision_os_get_post_deploy_status(self, params: dict) -> dict:
        """Return one post-deploy monitoring summary for the review surface."""
        model_id = str(params.get("modelId") or params.get("model_id") or "").strip()
        window = str(params.get("window") or "7d").strip()
        if not model_id:
            raise ValueError("modelId is required")
        try:
            return self._state.decision_os_get_post_deploy_status(model_id=model_id, window=window)
        except LookupError as exc:
            raise ValueError(str(exc)) from exc

    # -- Portfolio Manager RPC (Phase 10) ------------------------------------

    async def _portfolio_overview(self, params: dict) -> dict:
        """Return portfolio 4-quadrant overview for the control tower."""
        limit = int(params.get("limit") or 20)
        try:
            store = self._get_portfolio_store()
            from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant

            def _serialize(entries: list) -> list[dict]:
                return [
                    {
                        "entry_id": e.entry_id,
                        "task_contract_id": e.task_contract_id,
                        "quadrant": e.quadrant,
                        "priority": e.business_priority.value,
                        "sla_deadline": e.sla_deadline.isoformat() if e.sla_deadline else None,
                        "parent_run_id": e.parent_run_id,
                        "wait_condition_id": e.wait_condition_id,
                        "monitoring_metric_ref": e.monitoring_metric_ref,
                        "tags": e.tags,
                        "updated_at": e.updated_at.isoformat(),
                    }
                    for e in entries
                ]

            active = store.list_entries(quadrant=PortfolioQuadrant.ACTIVE, limit=limit)
            waiting = store.list_entries(quadrant=PortfolioQuadrant.WAITING, limit=limit)
            monitoring = store.list_entries(quadrant=PortfolioQuadrant.MONITORING, limit=limit)
            candidates = store.list_entries(
                quadrant=PortfolioQuadrant.PLAYBOOK_CANDIDATE,
                limit=limit,
            )

            from ds_agent.application.portfolio.slot_manager import SlotManager

            slots = SlotManager(store)

            return {
                "active": _serialize(active),
                "waiting": _serialize(waiting),
                "monitoring": _serialize(monitoring),
                "candidates": _serialize(candidates),
                "slots": {
                    "active": slots.active_count(),
                    "max": slots.max_slots,
                    "available": slots.available_slots(),
                },
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "active": [],
                "waiting": [],
                "monitoring": [],
                "candidates": [],
                "slots": {"active": 0, "max": 3, "available": 3},
            }

    async def _portfolio_pause(self, params: dict) -> dict:
        """Pause a portfolio entry via RPC."""
        entry_id = str(params.get("entryId") or "").strip()
        if not entry_id:
            raise ValueError("entryId is required")
        wait_kind = str(params.get("waitKind") or "timer")
        wait_spec = params.get("waitSpec") or {}
        reason = str(params.get("reason") or "paused via UI")

        import json as _json
        from datetime import UTC, datetime

        from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant, PortfolioTransition
        from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind

        store = self._get_portfolio_store()
        entry = store.get_entry(entry_id)
        if entry is None:
            raise ValueError(f"Portfolio entry {entry_id} not found")

        now = datetime.now(UTC)
        condition_id = f"WC-{now.strftime('%Y%m%d%H%M%S')}"
        kind = WaitConditionKind(wait_kind)
        spec = wait_spec if isinstance(wait_spec, dict) else _json.loads(str(wait_spec))

        updated = entry.transition_to(
            PortfolioQuadrant.WAITING,
            reason=reason,
            actor="user",
            now=now,
            wait_condition_id=condition_id,
        )
        store.save_wait_condition(
            WaitCondition.create(
                condition_id=condition_id,
                kind=kind,
                spec=spec,
                now=now,
            )
        )
        store.save_entry(updated)
        store.record_transition(
            entry_id,
            PortfolioTransition(
                from_quadrant=entry.quadrant,
                to_quadrant=PortfolioQuadrant.WAITING,
                reason=reason,
                actor="user",
                at=now,
            ),
        )
        return {"ok": True, "entryId": entry_id, "newQuadrant": "waiting"}

    async def _portfolio_resume(self, params: dict) -> dict:
        """Resume a waiting portfolio entry via RPC."""
        entry_id = str(params.get("entryId") or "").strip()
        run_id = str(params.get("runId") or "").strip()
        if not entry_id:
            raise ValueError("entryId is required")
        if not run_id:
            raise ValueError("runId is required")
        reason = str(params.get("reason") or "resumed via UI")

        from datetime import UTC, datetime

        from ds_agent.application.portfolio.slot_manager import SlotManager
        from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant, PortfolioTransition

        store = self._get_portfolio_store()
        entry = store.get_entry(entry_id)
        if entry is None:
            raise ValueError(f"Portfolio entry {entry_id} not found")

        slot_mgr = SlotManager(store)
        refusal = slot_mgr.acquire_or_refuse()
        if refusal:
            raise ValueError(refusal)

        now = datetime.now(UTC)
        updated = entry.transition_to(
            PortfolioQuadrant.ACTIVE,
            reason=reason,
            actor="user",
            now=now,
            run_id=run_id,
        )
        store.save_entry(updated)
        store.record_transition(
            entry_id,
            PortfolioTransition(
                from_quadrant=entry.quadrant,
                to_quadrant=PortfolioQuadrant.ACTIVE,
                reason=reason,
                actor="user",
                at=now,
            ),
        )
        return {"ok": True, "entryId": entry_id, "newQuadrant": "active"}

    async def _portfolio_set_sla(self, params: dict) -> dict:
        """Update SLA priority/deadline for a portfolio entry via RPC."""
        entry_id = str(params.get("entryId") or "").strip()
        priority = str(params.get("priority") or "").strip()
        deadline_str = str(params.get("deadline") or "").strip()
        if not entry_id:
            raise ValueError("entryId is required")
        if not priority:
            raise ValueError("priority is required")

        from datetime import UTC, datetime

        from ds_agent.domain.portfolio.portfolio_entry import BusinessPriority

        store = self._get_portfolio_store()
        entry = store.get_entry(entry_id)
        if entry is None:
            raise ValueError(f"Portfolio entry {entry_id} not found")

        bp = BusinessPriority(priority)
        sla_deadline = datetime.fromisoformat(deadline_str) if deadline_str else None
        updated = entry.model_copy(
            update={
                "business_priority": bp,
                "sla_deadline": sla_deadline,
                "updated_at": datetime.now(UTC),
            }
        )
        store.save_entry(updated)
        return {
            "ok": True,
            "entryId": entry_id,
            "priority": bp.value,
            "slaDeadline": sla_deadline.isoformat() if sla_deadline else None,
        }

    def _get_portfolio_store(self):
        """Lazy-load portfolio store."""
        if not hasattr(self, "_portfolio_store_cache"):
            from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore

            workspace = str(self._state.config.agent.workspace_dir)
            self._portfolio_store_cache = SqlitePortfolioStore.for_workspace(workspace)
        return self._portfolio_store_cache

    # -- Learning Governance RPC (Phase 12) -----------------------------------

    def _get_learning_store(self, *, require_mutation: bool = False):
        """Lazy-load learning store."""
        if require_mutation and not _self_improve_governance_enabled():
            raise ValueError("Self-improve governance is not enabled.")
        if not hasattr(self, "_learning_store_cache"):
            from ds_agent.infrastructure.persistence.learning_store import (
                SqliteLearningStore,
            )

            workspace = str(self._state.config.agent.workspace_dir)
            self._learning_store_cache = SqliteLearningStore.for_workspace(workspace)
        return self._learning_store_cache

    async def _learning_status(self, params: dict) -> dict:
        """Return read-only learning governance status."""

        history_limit = int(params.get("historyLimit") or 5)
        payload = build_learning_governance_status_payload(
            policy_store=self._state._policy_store,
            store=self._get_learning_store(),
            workspace_dir=str(self._state.config.agent.workspace_dir),
            history_limit=history_limit,
        )
        payload["reviewEnabled"] = _self_improve_governance_enabled()
        return payload

    async def _learning_inbox(self, params: dict) -> dict:
        """Return scored learning inbox items."""
        from datetime import UTC, datetime

        from ds_agent.application.learning.learning_inbox import LearningInboxUseCase
        from ds_agent.domain.learning.learning_item import (
            LearningItemStatus,
            LearningItemType,
        )

        class _Clock:
            def now(self) -> datetime:
                return datetime.now(UTC)

        store = self._get_learning_store()
        status = str(params.get("status") or "proposed")
        item_type = str(params.get("itemType") or "all")
        limit = int(params.get("limit") or 20)

        status_filter = None
        if status != "all":
            status_filter = [LearningItemStatus(status)]
        type_filter = LearningItemType(item_type) if item_type != "all" else None

        uc = LearningInboxUseCase(store, _Clock())
        scored = uc.execute(
            status_filter=status_filter,
            item_type_filter=type_filter,
            limit=limit,
        )
        return {
            "items": [
                _serialize_learning_item_summary(s.item, priority_score=s.priority_score)
                for s in scored
            ],
            "total": len(scored),
        }

    async def _learning_review(self, params: dict) -> dict:
        """Review one learning item."""
        from datetime import UTC, datetime

        from ds_agent.application.learning.review_learning_item import (
            ReviewLearningItemUseCase,
        )
        from ds_agent.domain.learning.review_event import (
            ReviewChecklist,
            ReviewDecision,
        )

        class _Clock:
            def now(self) -> datetime:
                return datetime.now(UTC)

        item_id = str(params.get("itemId") or "").strip()
        decision = str(params.get("decision") or "").strip()
        comment = str(params.get("comment") or "")
        if not item_id:
            raise ValueError("itemId is required")
        if not decision:
            raise ValueError("decision is required")

        dec = ReviewDecision(decision)
        checklist = (
            ReviewChecklist(
                evidence_sufficient=True,
                no_unresolved_conflicts=True,
                scope_appropriate=True,
                content_accurate=True,
            )
            if dec == ReviewDecision.APPROVE
            else None
        )

        store = self._get_learning_store(require_mutation=True)
        uc = ReviewLearningItemUseCase(store, _Clock())
        updated, event = uc.execute(
            item_id=item_id,
            decision=dec,
            reviewer="electron-operator",
            checklist=checklist,
            comment=comment,
        )
        return {
            "ok": True,
            "itemId": updated.item_id,
            "newStatus": updated.status.value,
            "eventId": event.event_id,
        }

    async def _learning_get_item(self, params: dict) -> dict:
        """Get one learning item detail."""
        item_id = str(params.get("itemId") or "").strip()
        if not item_id:
            raise ValueError("itemId is required")
        store = self._get_learning_store()
        item = store.get_item(item_id)
        if item is None:
            raise ValueError(f"Learning item {item_id} not found")
        return _serialize_learning_item_detail(item)

    async def _learning_promotions(self, params: dict) -> dict:
        """List promotion records."""
        store = self._get_learning_store()
        limit = int(params.get("limit") or 20)
        records = store.list_promotion_records(limit=limit)
        return {
            "records": [
                {
                    "record_id": r.record_id,
                    "item_id": r.item_id,
                    "type": r.item_type.value,
                    "eval_score": r.eval_score,
                    "promoted_at": r.promoted_at.isoformat(),
                }
                for r in records
            ],
        }

    async def _learning_deprecations(self, params: dict) -> dict:
        """List deprecation records."""
        store = self._get_learning_store()
        limit = int(params.get("limit") or 20)
        records = store.list_deprecation_records(limit=limit)
        return {
            "records": [
                {
                    "record_id": r.record_id,
                    "item_id": r.item_id,
                    "reason": r.reason.value,
                    "mode": r.mode.value,
                    "failure_count": r.failure_count,
                    "deprecated_at": r.deprecated_at.isoformat(),
                }
                for r in records
            ],
        }

    async def _learning_rollback(self, params: dict) -> dict:
        """Rollback a promoted learning item."""
        from datetime import UTC, datetime

        from ds_agent.application.learning.rollback_promotion import (
            RollbackPromotionUseCase,
        )

        class _Clock:
            def now(self) -> datetime:
                return datetime.now(UTC)

        item_id = str(params.get("itemId") or "").strip()
        reason = str(params.get("reason") or "rollback via UI")
        if not item_id:
            raise ValueError("itemId is required")

        store = self._get_learning_store(require_mutation=True)
        uc = RollbackPromotionUseCase(store, _Clock())
        updated, dep_record = uc.execute(item_id=item_id, reason=reason)
        return {
            "ok": True,
            "itemId": updated.item_id,
            "newStatus": updated.status.value,
            "deprecationRecordId": dep_record.record_id,
        }

    async def _learning_finalize_promotion(self, params: dict) -> dict:
        """Finalize one pending learning candidate."""

        from ds_agent.application.learning.finalize_learning_candidate_promotion import (
            FinalizeLearningCandidatePromotionUseCase,
        )

        candidate_id = str(params.get("candidateId") or "").strip()
        if not candidate_id:
            raise ValueError("candidateId is required")

        try:
            candidate_score = float(params.get("candidateScore"))
        except (TypeError, ValueError):
            raise ValueError("candidateScore must be a number") from None

        try:
            passed_tasks = int(params.get("passedTasks"))
        except (TypeError, ValueError):
            raise ValueError("passedTasks must be an integer") from None

        try:
            total_tasks = int(params.get("totalTasks"))
        except (TypeError, ValueError):
            raise ValueError("totalTasks must be an integer") from None

        decision, candidate = FinalizeLearningCandidatePromotionUseCase(
            str(self._state.config.agent.workspace_dir),
            active_custom_dir=_active_custom_skills_dir(),
        ).execute(
            candidate_id=candidate_id,
            candidate_score=candidate_score,
            passed_tasks=passed_tasks,
            total_tasks=total_tasks,
            baseline_score=_optional_float(params.get("baselineScore")),
            delta_threshold=_optional_float(params.get("deltaThreshold")) or 0.03,
        )
        return {
            "ok": True,
            "candidateId": decision.candidate_id,
            "status": decision.status,
            "promoted": decision.promoted,
            "candidateScore": decision.candidate_score,
            "baselineScore": decision.baseline_score,
            "deltaScore": decision.delta_score,
            "deltaThreshold": decision.delta_threshold,
            "passedTasks": decision.passed_tasks,
            "totalTasks": decision.total_tasks,
            "summary": decision.summary,
            "promotedPath": candidate.promoted_path,
            "pendingPath": candidate.pending_path,
        }

    async def _policy_set_action_matrix_overrides(self, params: dict) -> dict:
        """Replace persisted authority x action-class matrix overrides."""

        overrides = params.get("overrides")
        if not isinstance(overrides, dict):
            raise ValueError("overrides must be an object")

        normalized = self._state.set_action_matrix_overrides(
            {
                str(action_name): {
                    str(authority_name): str(verdict_name)
                    for authority_name, verdict_name in authority_map.items()
                    if isinstance(authority_map, dict)
                }
                for action_name, authority_map in overrides.items()
            }
        )
        return {
            "actionMatrixOverrides": normalized,
            "actionMatrixOverrideCount": sum(len(row) for row in normalized.values()),
        }

    async def _policy_matrix_get(self, _params: dict) -> dict:
        """Return the persisted risk-tier matrix and recent history."""
        from ds_agent.application.use_cases.risk_tier_matrix_usecases import (
            LoadRiskTierMatrixUseCase,
        )

        use_case = LoadRiskTierMatrixUseCase(self._state.policy_store)
        result = use_case.execute()
        return {
            "matrix": dict(result.matrix),
            "history": [
                {
                    "savedAt": snapshot.saved_at,
                    "matrix": dict(snapshot.matrix),
                    "savedBy": snapshot.saved_by,
                }
                for snapshot in result.history
            ],
        }

    async def _policy_matrix_save(self, params: dict) -> dict:
        """Persist a risk-tier matrix draft and return the saved snapshot."""
        from ds_agent.application.use_cases.risk_tier_matrix_usecases import (
            SaveRiskTierMatrixInput,
            SaveRiskTierMatrixUseCase,
        )

        matrix = params.get("matrix")
        if not isinstance(matrix, dict):
            raise ValueError("matrix must be an object")
        saved_by_raw = params.get("savedBy")
        saved_by = (
            str(saved_by_raw).strip()
            if isinstance(saved_by_raw, str) and saved_by_raw.strip()
            else None
        )

        use_case = SaveRiskTierMatrixUseCase(self._state.policy_store)
        snapshot = use_case.execute(SaveRiskTierMatrixInput(matrix=matrix, saved_by=saved_by))
        return {
            "snapshot": {
                "savedAt": snapshot.saved_at,
                "matrix": dict(snapshot.matrix),
                "savedBy": snapshot.saved_by,
            },
        }

    async def _policy_matrix_preview(self, params: dict) -> dict:
        """Build a history-backed impact preview for a candidate matrix."""
        from ds_agent.application.use_cases.risk_tier_matrix_usecases import (
            BuildHistoryBackedImpactPreview,
            HistoryBackedImpactPreviewInput,
        )

        candidate = params.get("candidateMatrix")
        if not isinstance(candidate, dict):
            raise ValueError("candidateMatrix must be an object")

        use_case = BuildHistoryBackedImpactPreview(self._state.policy_store)
        result = use_case.execute(HistoryBackedImpactPreviewInput(candidate_matrix=candidate))
        return {
            "addedRows": list(result.added_rows),
            "removedRows": list(result.removed_rows),
            "modifiedRows": list(result.modified_rows),
            "historicalCounts": dict(result.historical_counts),
        }

    async def _files_list(self, params: dict) -> dict:
        """List files in the project workspace."""
        project_id = params.get("projectId")
        # 4.9 fix: run blocking rglob in a thread to avoid event loop stall
        files = await asyncio.to_thread(self._state.list_files, project_id)
        return {"files": files}

    async def _files_delete(self, params: dict) -> dict:
        """Delete one file or one empty directory inside the workspace.

        Emits ``workspace.changed`` + ``file.deleted`` so every connected
        frontend refreshes its file list — without this the sidebar gets
        out of sync with disk until the next manual reload.
        """
        rel_path = (params.get("path") or "").strip()
        if not rel_path:
            raise ValueError("path is required")

        result = await asyncio.to_thread(self._state.delete_file, rel_path)
        # emit_event is sync fire-and-forget (schedules a background send)
        self._callbacks.emit_event("workspace.changed", {"reason": "delete"})
        self._callbacks.emit_event("file.deleted", {"path": rel_path, "kind": result.get("kind")})
        return result

    async def _files_export(self, params: dict) -> dict:
        """Export a workspace file to PDF / DOCX / HTML / XLSX / IPYNB (P1-12)."""
        rel_path = (params.get("path") or "").strip()
        if not rel_path:
            raise ValueError("path is required")
        fmt = (params.get("format") or "").strip().lower()
        if not fmt:
            raise ValueError("format is required")
        return await asyncio.to_thread(self._state.export_file, rel_path, fmt)

    async def _files_preview(self, params: dict) -> dict:
        """Return a safe preview of a workspace file (CSV head or text)."""
        rel_path = (params.get("path") or "").strip()
        if not rel_path:
            raise ValueError("path is required")
        rows = int(params.get("rows") or 20)
        sheet_name = str(params.get("sheetName")).strip() if params.get("sheetName") else None
        header_row = int(params.get("headerRow") or 1)
        return await asyncio.to_thread(
            self._state.preview_file,
            rel_path,
            rows,
            sheet_name=sheet_name,
            header_row=header_row,
        )

    # SEC-03: File upload validation constants
    _MAX_UPLOAD_SIZE: ClassVar[int] = 100 * 1024 * 1024  # 100MB
    _ALLOWED_UPLOAD_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {
            ".csv",
            ".tsv",
            ".xlsx",
            ".xls",
            ".json",
            ".parquet",
            ".pq",
            ".txt",
            ".md",
            ".py",
            ".yaml",
            ".yml",
            ".toml",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".svg",
            ".webp",
        }
    )

    async def _files_upload(self, params: dict) -> dict:
        """Receive a base64-encoded file upload with validation."""
        import base64
        import binascii
        from pathlib import Path

        name = params.get("name", "").strip()
        data_b64 = params.get("data", "")
        if not name or not data_b64:
            raise ValueError("name and data are required")

        # SEC-03: Validate filename — no path traversal
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError("Invalid filename: path separators not allowed")

        # SEC-03: Validate file extension
        ext = Path(name).suffix.lower()
        if ext not in self._ALLOWED_UPLOAD_EXTENSIONS:
            raise ValueError(f"File type not allowed: {ext}")

        # SEC-03: Validate file size before decoding
        estimated_size = len(data_b64) * 3 // 4
        if estimated_size > self._MAX_UPLOAD_SIZE:
            max_mb = self._MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ValueError(f"File too large: {estimated_size} bytes (max {max_mb}MB)")

        workspace = Path(self._state.config.agent.workspace_dir).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        dest = (workspace / name).resolve()

        # SEC-03: Double-check resolved path is under workspace (is_relative_to, not startswith)
        if not dest.is_relative_to(workspace):
            raise ValueError("Path traversal detected")

        try:
            decoded = base64.b64decode(data_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64 data: {e}") from e
        if len(decoded) > self._MAX_UPLOAD_SIZE:
            max_mb = self._MAX_UPLOAD_SIZE // (1024 * 1024)
            raise ValueError(f"File too large after decode: {len(decoded)} bytes (max {max_mb}MB)")

        dest.write_bytes(decoded)

        return {"path": str(dest)}

    async def _provider_list(self, _params: dict) -> dict:
        """List available providers."""
        return {
            "providers": [
                {"id": "anthropic", "name": "Anthropic (Claude)", "type": "api_key"},
                {"id": "openai", "name": "OpenAI (GPT)", "type": "api_key"},
                {"id": "codex", "name": "ChatGPT (Codex OAuth)", "type": "oauth"},
                {"id": "gemini", "name": "Google Gemini", "type": "oauth"},
                {"id": "deepseek", "name": "DeepSeek", "type": "api_key"},
                {"id": "minimax", "name": "MiniMax", "type": "api_key"},
                {"id": "qwen", "name": "Qwen (Alibaba)", "type": "api_key"},
                {"id": "zhipu", "name": "Zhipu (GLM)", "type": "api_key"},
                {"id": "moonshot", "name": "Moonshot (Kimi)", "type": "api_key"},
                {"id": "groq", "name": "Groq (Free)", "type": "free_api_key"},
                {"id": "ollama", "name": "Ollama (Local)", "type": "local"},
            ]
        }

    async def _provider_models(self, _params: dict) -> dict:
        """Return full model catalog with metadata."""
        from ds_agent.providers.anthropic import ANTHROPIC_MODELS
        from ds_agent.providers.codex_oauth import CODEX_MODELS
        from ds_agent.providers.gemini_oauth import GEMINI_MODELS
        from ds_agent.providers.litellm_provider import LITELLM_MODELS
        from ds_agent.providers.model_metadata import derive_capability_metadata
        from ds_agent.providers.openai_provider import OPENAI_MODELS

        catalog: list[dict] = []

        def _enrich(entry: dict) -> dict:
            metadata = derive_capability_metadata(
                model_id=entry["id"],
                provider=entry["provider"],
                display_name=entry["displayName"],
                max_context=entry["maxContext"],
                auth_type=entry["authType"],
                legacy=entry["legacy"],
            )
            entry.update(metadata.to_dict())
            return entry

        # Anthropic
        for model_id, meta in ANTHROPIC_MODELS.items():
            catalog.append(
                _enrich(
                    {
                        "id": f"anthropic/{model_id}",
                        "provider": "anthropic",
                        "displayName": meta["display_name"],
                        "maxContext": meta["max_context"],
                        "maxOutput": meta["max_output"],
                        "authType": "api_key",
                        "legacy": meta.get("legacy", False),
                    }
                )
            )

        # OpenAI
        for model_id, meta in OPENAI_MODELS.items():
            catalog.append(
                _enrich(
                    {
                        "id": f"openai/{model_id}",
                        "provider": "openai",
                        "displayName": meta["display_name"],
                        "maxContext": meta["max_context"],
                        "maxOutput": meta["max_output"],
                        "authType": "api_key",
                        "legacy": meta.get("legacy", False),
                    }
                )
            )

        # Codex OAuth
        for model_id, meta in CODEX_MODELS.items():
            catalog.append(
                _enrich(
                    {
                        "id": f"codex/{model_id}",
                        "provider": "codex",
                        "displayName": f"{meta['display_name']} (Codex)",
                        "maxContext": meta["max_context"],
                        "maxOutput": meta["max_output"],
                        "authType": "oauth",
                        "legacy": meta.get("legacy", False),
                    }
                )
            )

        # Gemini OAuth
        for model_id, meta in GEMINI_MODELS.items():
            catalog.append(
                _enrich(
                    {
                        "id": f"gemini/{model_id}",
                        "provider": "gemini",
                        "displayName": meta["display_name"],
                        "maxContext": meta["max_context"],
                        "maxOutput": meta["max_output"],
                        "authType": "oauth",
                        "legacy": meta.get("legacy", False),
                    }
                )
            )

        # LiteLLM (Chinese providers, Groq, etc.)
        for model_id, meta in LITELLM_MODELS.items():
            catalog.append(
                _enrich(
                    {
                        "id": model_id,
                        "provider": meta.get("provider", "litellm"),
                        "displayName": meta["display_name"],
                        "maxContext": meta["max_context"],
                        "maxOutput": meta["max_output"],
                        "authType": meta.get("auth_type", "api_key"),
                        "legacy": meta.get("legacy", False),
                    }
                )
            )

        return {"models": catalog}

    # SEC-11: Known provider names for API key validation
    _KNOWN_PROVIDERS: ClassVar[frozenset[str]] = frozenset(
        {
            "anthropic",
            "openai",
            "deepseek",
            "minimax",
            "qwen",
            "zhipu",
            "moonshot",
            "groq",
            "gemini",
            "codex",
            "ollama",
        }
    )

    async def _config_set_api_key(self, params: dict) -> dict:
        """Store an API key for a provider (validated provider name)."""
        provider = params.get("provider", "").strip().lower()
        key = params.get("key", "")
        if not provider or not key:
            raise ValueError("provider and key are required")

        if provider not in self._KNOWN_PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")

        self._state.config_manager.set_api_key(provider, key)
        return {"ok": True}

    async def _config_get_api_keys(self, _params: dict) -> dict:
        """Return configured API keys (masked for security)."""
        return {"keys": self._state.config_manager.get_api_keys_masked()}

    async def _provider_auth_status(self, _params: dict) -> dict:
        """Check authentication status for all providers."""
        from ds_agent.runtime.provider_factory import get_provider_auth_statuses

        return {
            "statuses": get_provider_auth_statuses(
                self._state.config,
                token_store=self._state.token_store,
            )
        }

    async def _provider_health(self, _params: dict) -> dict:
        """Return provider health snapshots for product surfaces."""
        from ds_agent.runtime.provider_factory import get_provider_health_snapshot

        return {
            "providers": await get_provider_health_snapshot(
                self._state.config,
                token_store=self._state.token_store,
            )
        }

    async def _project_list(self, _params: dict) -> dict:
        """List projects."""
        return {"projects": self._state.list_projects()}

    async def _project_create(self, params: dict) -> dict:
        """Create a new project."""
        name = params.get("name", "Untitled")
        task_type = params.get("taskType")
        project_id = self._state.create_project(name, task_type)
        return {"projectId": project_id}

    # -- OAuth RPC methods -----------------------------------------------------

    _OAUTH_PROVIDERS: ClassVar[frozenset[str]] = frozenset({"codex", "gemini"})

    async def _oauth_start_login(self, params: dict) -> dict:
        """Start OAuth login for a provider. Opens browser for consent."""
        provider = params.get("provider", "").strip().lower()
        if provider not in self._OAUTH_PROVIDERS:
            raise ValueError(f"Unknown OAuth provider: {provider}")

        oauth = self._state.oauth_service
        if provider == "gemini":
            result = await oauth.start_gemini_login()

            # Background: wait for callback and emit completion event
            async def _emit_on_complete() -> None:
                try:
                    tokens = await oauth.wait_for_login("gemini")
                    self._callbacks.emit_event(
                        "oauth.complete",
                        {
                            "provider": "gemini",
                            "success": True,
                            "email": tokens.email,
                        },
                    )
                except Exception as e:
                    logger.error("oauth_login_failed", provider="gemini", error=str(e))
                    self._callbacks.emit_event(
                        "oauth.complete",
                        {
                            "provider": "gemini",
                            "success": False,
                            "error": str(e),
                        },
                    )

            task = asyncio.create_task(_emit_on_complete())
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            return {"authUrl": result["auth_url"], "provider": "gemini"}

        else:  # codex
            try:
                tokens = await oauth.start_codex_login()
                # Codex login is synchronous (file read or CLI wait)
                self._callbacks.emit_event(
                    "oauth.complete",
                    {
                        "provider": "codex",
                        "success": True,
                        "email": None,
                        "account_id": tokens.account_id,
                    },
                )
                return {"provider": "codex", "authUrl": ""}
            except Exception as e:
                self._callbacks.emit_event(
                    "oauth.complete",
                    {
                        "provider": "codex",
                        "success": False,
                        "error": str(e),
                    },
                )
                raise

    async def _oauth_status(self, _params: dict) -> dict:
        """Return OAuth status for all providers."""
        oauth = self._state.oauth_service
        return {
            "providers": {
                "codex": oauth.get_status("codex"),
                "gemini": oauth.get_status("gemini"),
            }
        }

    async def _oauth_disconnect(self, params: dict) -> dict:
        """Disconnect (revoke) OAuth for a provider."""
        provider = params.get("provider", "").strip().lower()
        if provider not in self._OAUTH_PROVIDERS:
            raise ValueError(f"Unknown OAuth provider: {provider}")
        self._state.oauth_service.disconnect(provider)
        return {"ok": True}

    async def _connector_list(self, params: dict) -> dict:
        """Return configured connectors and policy gating state."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        return await asyncio.to_thread(self._state.list_connectors, actor_id=actor_id)

    async def _connector_test(self, params: dict) -> dict:
        """Run a read-only connector probe without persisting secrets."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        return await asyncio.to_thread(self._state.test_connector, params, actor_id=actor_id)

    async def _connector_save(self, params: dict) -> dict:
        """Persist one connector definition and its secret payload."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        return await asyncio.to_thread(self._state.save_connector, params, actor_id=actor_id)

    async def _connector_delete(self, params: dict) -> dict:
        """Delete one connector and its stored credential."""
        actor_id = str(params.get("actorId") or _DEFAULT_ORG_ACTOR)
        name = _normalize_connector_name(params.get("name"))
        return await asyncio.to_thread(self._state.delete_connector, name, actor_id=actor_id)

    async def _run_scorecard(self, params: dict) -> dict:
        """Build an evaluation scorecard for one tracked run."""
        run_id = str(params.get("runId", "")).strip()
        if not run_id:
            raise ValueError("runId is required")
        return {
            "scorecard": await asyncio.to_thread(self._state.get_run_scorecard, run_id),
        }

    async def _run_submit_human_rubric(self, params: dict) -> dict:
        """Persist one human rubric review and return the updated scorecard."""
        run_id = str(params.get("runId", "")).strip()
        reviewer_id = str(params.get("reviewerId", "")).strip()
        dimensions = params.get("dimensions")
        comment = params.get("comment")
        if not run_id:
            raise ValueError("runId is required")
        if not reviewer_id:
            raise ValueError("reviewerId is required")
        if not isinstance(dimensions, dict) or not dimensions:
            raise ValueError("dimensions must be a non-empty object")
        return {
            "scorecard": await asyncio.to_thread(
                self._state.submit_run_human_rubric,
                run_id,
                reviewer_id,
                {str(key): float(value) for key, value in dimensions.items()},
                None if comment is None else str(comment),
            ),
        }

    async def _run_shadow_compare(self, params: dict) -> dict:
        """Execute one shadow run for a tracked production run and return the new scorecard."""
        run_id = str(params.get("runId", "")).strip()
        model = params.get("model")
        shadow_factor = params.get("shadowFactor", 0.5)
        if not run_id:
            raise ValueError("runId is required")
        try:
            resolved_factor = float(shadow_factor)
        except (TypeError, ValueError) as exc:
            raise ValueError("shadowFactor must be a number") from exc
        if resolved_factor <= 0:
            raise ValueError("shadowFactor must be greater than 0")
        return {
            "scorecard": await asyncio.to_thread(
                self._state.run_shadow_compare,
                run_id,
                None if model is None else str(model),
                resolved_factor,
            ),
        }

    async def _eval_regression_board(self, params: dict) -> dict:
        """Return the latest evaluation regression-board snapshot."""
        mode = params.get("mode")
        domain = params.get("domain")
        recent_window = params.get("recentWindow", 3)
        baseline_window_days = params.get("baselineWindowDays", 14)
        try:
            resolved_recent_window = int(recent_window)
        except (TypeError, ValueError) as exc:
            raise ValueError("recentWindow must be an integer") from exc
        try:
            resolved_baseline_days = int(baseline_window_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("baselineWindowDays must be an integer") from exc
        if resolved_recent_window <= 0:
            raise ValueError("recentWindow must be greater than 0")
        if resolved_baseline_days <= 0:
            raise ValueError("baselineWindowDays must be greater than 0")
        return {
            "board": await asyncio.to_thread(
                self._state.get_regression_board,
                None if mode is None else str(mode),
                None if domain is None else str(domain),
                resolved_recent_window,
                resolved_baseline_days,
            ),
        }

    async def _eval_freeze_regression_baseline(self, params: dict) -> dict:
        """Persist one frozen regression baseline and return the refreshed board."""
        commit_sha = str(params.get("commitSha", "")).strip()
        mode = params.get("mode")
        domain = params.get("domain")
        recent_window = params.get("recentWindow", 3)
        baseline_window_days = params.get("baselineWindowDays", 14)
        window_days = params.get("windowDays")
        if not commit_sha:
            raise ValueError("commitSha is required")
        try:
            resolved_recent_window = int(recent_window)
        except (TypeError, ValueError) as exc:
            raise ValueError("recentWindow must be an integer") from exc
        try:
            resolved_baseline_days = int(baseline_window_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("baselineWindowDays must be an integer") from exc
        resolved_window_days: int | None
        if window_days is None:
            resolved_window_days = None
        else:
            try:
                resolved_window_days = int(window_days)
            except (TypeError, ValueError) as exc:
                raise ValueError("windowDays must be an integer") from exc
        if resolved_recent_window <= 0:
            raise ValueError("recentWindow must be greater than 0")
        if resolved_baseline_days <= 0:
            raise ValueError("baselineWindowDays must be greater than 0")
        if resolved_window_days is not None and resolved_window_days <= 0:
            raise ValueError("windowDays must be greater than 0")
        return await asyncio.to_thread(
            self._state.freeze_regression_baseline,
            commit_sha,
            None if mode is None else str(mode),
            None if domain is None else str(domain),
            resolved_recent_window,
            resolved_baseline_days,
            resolved_window_days,
        )

    # -- Method routing table ---------------------------------------------------

    _METHOD_MAP: ClassVar[dict[str, Any]] = {
        "chat.send": _chat_send,
        "chat.abort": _chat_abort,
        "chat.history": _chat_history,
        "org.get": _org_get,
        "org.updateSettings": _org_update_settings,
        "org.inviteMember": _org_invite_member,
        "org.updateMemberRole": _org_update_member_role,
        "org.auditLogExport": _org_audit_log_export,
        "skill.catalog": _skill_catalog,
        "skill.get": _skill_get,
        "skill.save": _skill_save,
        "skill.importMarkdown": _skill_import_markdown,
        "skill.importUrl": _skill_import_url,
        "skill.delete": _skill_delete,
        "skill.toggle": _skill_toggle,
        "semantic.lookupMetric": _semantic_lookup_metric,
        "semantic.getTrust": _semantic_get_trust,
        "semantic.getVerifiedQuery": _semantic_get_verified_query,
        "semantic.loadPack": _semantic_load_pack,
        "semantic.listSnapshots": _semantic_list_snapshots,
        "semantic.restoreSnapshot": _semantic_restore_snapshot,
        "semantic.syncSource": _semantic_sync_source,
        "run.start": _run_start,
        "run.wait": _run_wait,
        "run.abort": _run_abort,
        "run.list": _run_list,
        "run.branch": _run_branch,
        "run.rerun": _run_rerun,
        "run.promote": _run_promote,
        "run.list_promoted": _run_list_promoted,
        "checkpoint.save": _checkpoint_save,
        "checkpoint.list": _checkpoint_list,
        "runs.list_lineage": _runs_list_lineage,
        "run.scorecard": _run_scorecard,
        "run.submitHumanRubric": _run_submit_human_rubric,
        "run.shadowCompare": _run_shadow_compare,
        "eval.regressionBoard": _eval_regression_board,
        "eval.freezeRegressionBaseline": _eval_freeze_regression_baseline,
        "session.list": _session_list,
        "task.list": _task_list,
        "runtime.events.list": _runtime_events_list,
        "approval.list": _approval_list,
        "approval.get": _approval_get,
        "approval.submit": _approval_submit,
        "approval.resolve": _approval_resolve,
        "policy.get": _policy_get,
        "policy.upsertRecurringGoal": _policy_upsert_recurring_goal,
        "policy.setStandingOrders": _policy_set_standing_orders,
        "policy.setActionMatrixOverrides": _policy_set_action_matrix_overrides,
        "policy.matrix.get": _policy_matrix_get,
        "policy.matrix.save": _policy_matrix_save,
        "policy.matrix.preview": _policy_matrix_preview,
        "decisionOs.overview": _decision_os_overview,
        "decisionOs.compareRuns": _decision_os_compare_runs,
        "decisionOs.requestPromotion": _decision_os_request_promotion,
        "decisionOs.resolvePromotion": _decision_os_resolve_promotion,
        "decisionOs.applyPromotion": _decision_os_apply_promotion,
        "decisionOs.getPostDeployStatus": _decision_os_get_post_deploy_status,
        "portfolio.overview": _portfolio_overview,
        "portfolio.pause": _portfolio_pause,
        "portfolio.resume": _portfolio_resume,
        "portfolio.setSla": _portfolio_set_sla,
        "learning.status": _learning_status,
        "learning.inbox": _learning_inbox,
        "learning.review": _learning_review,
        "learning.getItem": _learning_get_item,
        "learning.promotions": _learning_promotions,
        "learning.deprecations": _learning_deprecations,
        "learning.rollback": _learning_rollback,
        "learning.finalizePromotion": _learning_finalize_promotion,
        "config.get": _config_get,
        "config.set": _config_set,
        "status.get": _status_get,
        "usage.summary": _usage_summary,
        "files.list": _files_list,
        "files.upload": _files_upload,
        "files.delete": _files_delete,
        "files.preview": _files_preview,
        "files.export": _files_export,
        "provider.list": _provider_list,
        "provider.models": _provider_models,
        "provider.authStatus": _provider_auth_status,
        "provider.health": _provider_health,
        "config.setApiKey": _config_set_api_key,
        "config.getApiKeys": _config_get_api_keys,
        "project.list": _project_list,
        "project.create": _project_create,
        "oauth.startLogin": _oauth_start_login,
        "oauth.status": _oauth_status,
        "oauth.disconnect": _oauth_disconnect,
        "connector.list": _connector_list,
        "connector.test": _connector_test,
        "connector.save": _connector_save,
        "connector.delete": _connector_delete,
    }

    # -- Internal helpers -------------------------------------------------------

    async def _send_ok(self, req_id: str, payload: dict) -> None:
        await self._ws.send_json(
            {
                "type": "res",
                "id": req_id,
                "ok": True,
                "payload": payload,
            }
        )

    async def _send_error(self, req_id: str, code: str, message: str) -> None:
        await self._ws.send_json(
            {
                "type": "res",
                "id": req_id,
                "ok": False,
                "error": {"code": code, "message": message},
            }
        )

    @staticmethod
    def _serialize_session_context(session_id: str) -> dict[str, str | None]:
        """Expose transport-friendly session metadata for runtime surfaces."""
        if session_id.startswith("telegram:"):
            conversation_id, thread_id = parse_telegram_session_id(session_id)
            if thread_id is not None:
                return {
                    "conversationId": conversation_id,
                    "threadId": thread_id,
                    "threadLabel": f"topic {thread_id}",
                    "sessionLabel": f"chat {conversation_id} / topic {thread_id}",
                }
            return {
                "conversationId": conversation_id,
                "threadId": None,
                "threadLabel": "main chat",
                "sessionLabel": f"chat {conversation_id}",
            }
        return {
            "conversationId": None,
            "threadId": None,
            "threadLabel": None,
            "sessionLabel": session_id,
        }

    @staticmethod
    def _serialize_run(run: RunState) -> dict:
        """Convert internal runtime state to RPC payload format."""
        return {
            "runId": run.run_id,
            "sessionId": run.session_id,
            **WsRpcHandler._serialize_session_context(run.session_id),
            "surface": run.surface,
            "status": run.status.value,
            "message": run.message,
            "taskId": run.task_id,
            "error": run.error,
            "resultPreview": run.result_preview,
            "costUsd": run.cost_usd,
            "createdAt": run.created_at,
            "startedAt": run.started_at,
            "finishedAt": run.finished_at,
            "resumedFromCheckpoint": bool(getattr(run, "resumed_from_checkpoint", False)),
            "branchedFromRunId": getattr(run, "branched_from_run_id", None),
            "rerunFromNodeId": getattr(run, "rerun_from_node_id", None),
        }

    @staticmethod
    def _serialize_session(session: RuntimeSession) -> dict:
        """Convert session state to RPC payload format."""
        return {
            "sessionId": session.session_id,
            **WsRpcHandler._serialize_session_context(session.session_id),
            "surface": session.surface,
            "createdAt": session.created_at,
            "lastActive": session.last_active,
            "lastRunId": session.last_run_id,
        }

    @staticmethod
    def _serialize_task(task: TaskState) -> dict:
        """Convert task state to RPC payload format."""
        return {
            "taskId": task.task_id,
            "runId": task.run_id,
            "status": task.status.value,
            "createdAt": task.created_at,
            "startedAt": task.started_at,
            "finishedAt": task.finished_at,
            "error": task.error,
        }

    @staticmethod
    def _serialize_approval(approval: object) -> dict:
        """Convert approval state to RPC payload format."""
        return serialize_approval(approval)

    @staticmethod
    def _serialize_recurring_goal(goal: object) -> dict:
        """Convert recurring-goal state to RPC payload format."""
        return {
            "goalId": getattr(goal, "goal_id", ""),
            "sessionId": getattr(goal, "session_id", ""),
            "prompt": getattr(goal, "prompt", ""),
            "intervalSeconds": getattr(goal, "interval_seconds", 0.0),
            "enabled": bool(getattr(goal, "enabled", True)),
            "lastTriggeredAt": getattr(goal, "last_triggered_at", None),
            "createdAt": getattr(goal, "created_at", 0.0),
            "updatedAt": getattr(goal, "updated_at", 0.0),
        }

    @staticmethod
    def _serialize_action_matrix_row(
        action_name: str,
        *,
        effective_row: dict,
        default_row: dict,
        override_row: dict[str, str],
    ) -> dict:
        """Convert one action-matrix row to RPC payload format."""

        from ds_agent.domain.value_objects.action_class import get_action_class

        action_class = get_action_class(action_name)
        return {
            "actionClass": action_name,
            "dataSensitivity": action_class.data_sensitivity.value,
            "writeSideEffect": action_class.write_side_effect.value,
            "costImpact": action_class.cost_impact.value,
            "reversibility": action_class.reversibility.value,
            "auditRequired": action_class.audit_required,
            "defaultVerdicts": {
                authority.value: verdict.value for authority, verdict in default_row.items()
            },
            "effectiveVerdicts": {
                authority.value: verdict.value for authority, verdict in effective_row.items()
            },
            "overrideVerdicts": dict(override_row),
        }


class AppState:
    """Thin facade over ConfigManager, AgentSessionRegistry, WorkspaceService.

    Created once at FastAPI startup, passed to each WsRpcHandler.
    Delegates all work to single-responsibility manager classes (4.1.4 fix).
    """

    def __init__(self, config: object | None = None) -> None:
        from ds_agent.api.agent_session_registry import AgentSessionRegistry
        from ds_agent.api.config_manager import ConfigManager
        from ds_agent.api.workspace_service import WorkspaceService
        from ds_agent.application.services.organization_policy import OrgPolicyGate
        from ds_agent.application.services.usage_summary import UsageSummaryService
        from ds_agent.config.schema import DSAgentConfig, WarehouseConnectorSettings
        from ds_agent.infrastructure.auth.oauth_service import OAuthService
        from ds_agent.infrastructure.persistence.access_log import JsonAccessLogStore
        from ds_agent.infrastructure.persistence.access_policy_store import (
            JsonAccessPolicyStore,
        )
        from ds_agent.infrastructure.persistence.card_store import SqliteCardStore
        from ds_agent.infrastructure.persistence.connector_factory import create_connector_adapter
        from ds_agent.infrastructure.secrets.connector_secret_manager import (
            create_connector_secret_manager,
        )
        from ds_agent.runtime.approval_grant_store import JsonApprovalGrantStore
        from ds_agent.runtime.approval_store import JsonApprovalStore
        from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
        from ds_agent.runtime.goal_store import JsonGoalStore
        from ds_agent.runtime.organization_store import JsonOrganizationStore
        from ds_agent.runtime.policy_store import JsonPolicyStore
        from ds_agent.runtime.provider_factory import create_auth_profile_store
        from ds_agent.runtime.run_registry import RunRegistry
        from ds_agent.runtime.runtime_event_log import RuntimeEventLog
        from ds_agent.runtime.session_registry import RuntimeSessionRegistry
        from ds_agent.runtime.task_ledger import TaskLedger
        from ds_agent.runtime.transcript_store import JsonTranscriptStore
        from ds_agent.skills.hub import SkillHub

        # Build the appropriate DSAgentConfig instance
        if config is None:
            self._config_manager = ConfigManager()
        elif isinstance(config, DSAgentConfig):
            self._config_manager = ConfigManager(config)
        else:
            self._config_manager = ConfigManager(DSAgentConfig())

        self._workspace = WorkspaceService(str(self.config.agent.workspace_dir))
        self._connector_settings_model = WarehouseConnectorSettings
        self._connector_adapter_factory = create_connector_adapter
        self._connector_secrets = create_connector_secret_manager()
        self._transcript_store = JsonTranscriptStore(self.config.agent.workspace_dir)
        self._checkpoint_store = JsonCheckpointStore(self.config.agent.workspace_dir)
        self._result_card_store = SqliteCardStore.for_workspace(self.config.agent.workspace_dir)
        self._goal_store = JsonGoalStore(self.config.agent.workspace_dir)
        self._approval_store = JsonApprovalStore(self.config.agent.workspace_dir)
        self._approval_grant_store = JsonApprovalGrantStore(self.config.agent.workspace_dir)
        self._organization_store = JsonOrganizationStore(self.config.agent.workspace_dir)
        self._usage_summary_service = UsageSummaryService(self._organization_store)
        self._org_policy_gate = OrgPolicyGate()
        self._policy_store = JsonPolicyStore(self.config.agent.workspace_dir)
        self._runtime_event_log = RuntimeEventLog(self.config.agent.workspace_dir)
        from ds_agent.runtime.promoted_artifact_store import JsonPromotedArtifactStore

        self._promoted_artifact_store = JsonPromotedArtifactStore(
            self.config.agent.workspace_dir,
        )
        self._runtime_event_listeners: set[Callable[[str, dict], None]] = set()
        self._autonomous_daemon: Any | None = None
        self._semantic_memory_container: Any | None = None
        self._decision_os_container: Any | None = None
        self._skill_hub = SkillHub.from_directories(
            [_BUILTIN_SKILLS_DIR, _SHARED_SKILLS_DIR, _CUSTOM_SKILLS_DIR]
        )

        # OAuth service — auth profile store + OAuth flow orchestrator
        oauth_cfg = getattr(self.config, "oauth", None)
        self._token_store = create_auth_profile_store(self.config)
        self._oauth_service = OAuthService(
            store=self._token_store,
            gemini_client_id=getattr(oauth_cfg, "gemini_client_id", "") if oauth_cfg else "",
            gemini_client_secret=(
                getattr(oauth_cfg, "gemini_client_secret", "") if oauth_cfg else ""
            ),
        )

        # Session registry — pass token_store so providers can use OAuth tokens
        self._sessions = AgentSessionRegistry(
            self.config,
            token_store=self._token_store,
            transcript_store=self._transcript_store,
            checkpoint_store=self._checkpoint_store,
            result_card_store=self._result_card_store,
            approval_store=self._approval_store,
            skill_hub=self._skill_hub,
            org_policy_supplier=self._organization_store.get,
        )
        self._runtime_sessions = RuntimeSessionRegistry(self.config.agent.workspace_dir)
        self._task_ledger = TaskLedger(self.config.agent.workspace_dir)
        self._runs = RunRegistry(self._runtime_sessions, self.config.agent.workspace_dir)
        from ds_agent.evaluation.infrastructure.persistence.jsonl_review_sampling_store import (
            JsonlReviewSamplingStore,
        )

        self._review_sampling_store = JsonlReviewSamplingStore.for_workspace(
            self.config.agent.workspace_dir
        )
        self._access_policy_store = JsonAccessPolicyStore(self.config.agent.workspace_dir)
        self._access_log_store = JsonAccessLogStore(self.config.agent.workspace_dir)
        from ds_agent.api.access_middleware import build_resource_access_guard

        self._resource_access_guard = build_resource_access_guard(
            policy_store=self._access_policy_store,
            log_store=self._access_log_store,
        )

        # ----- Web push (Wave 4 PLAN_06b infrastructure close) ---------
        # Subscription store: per-operator JSON files under workspace.
        from ds_agent.application.use_cases.dispatch_web_push_usecase import (
            DispatchWebPushUseCase,
        )
        from ds_agent.infrastructure.notification.web_push_transport import (
            build_web_push_transport,
        )
        from ds_agent.infrastructure.persistence.web_push_subscription_store import (
            JsonWebPushSubscriptionStore,
        )
        from ds_agent.runtime.web_push_keys import (
            VapidKeys,
            load_vapid_keys,
            load_vapid_subject,
        )
        from ds_agent.runtime.web_push_metrics import JsonWebPushMetricsStore
        from ds_agent.runtime.web_push_subject_store import JsonWebPushSubjectStore

        self._web_push_subscription_store = JsonWebPushSubscriptionStore(
            self.config.agent.workspace_dir,
        )
        self._web_push_subject_store = JsonWebPushSubjectStore(
            self.config.agent.workspace_dir,
        )
        self._web_push_metrics_store = JsonWebPushMetricsStore(
            self.config.agent.workspace_dir,
        )

        loaded_keys = load_vapid_keys(self.config.agent.workspace_dir)
        self._vapid_public_key: str | None
        if isinstance(loaded_keys, VapidKeys):
            self._vapid_public_key = loaded_keys.public_key_b64url

            def _on_subscription_expired(operator_id: str, endpoint: str) -> None:
                # The store ignores unknown endpoints idempotently, so the
                # callback is safe to invoke for races where two pushes
                # discover the same expired subscription.
                self._web_push_subscription_store.unregister(operator_id, endpoint)

            def _on_delivery_recorded(operator_id: str, endpoint: str, ok: bool) -> None:
                self._web_push_metrics_store.record_delivery(operator_id, endpoint, ok)

            def _on_subscription_pruned(
                operator_id: str,
                endpoint: str,
                reason: str,
            ) -> None:
                self._web_push_metrics_store.record_prune(operator_id, endpoint, reason)

            self._web_push_transport = build_web_push_transport(
                private_key_pem=loaded_keys.private_key_pem,
                public_key_b64url=loaded_keys.public_key_b64url,
                subject=loaded_keys.subject,
                subject_provider=lambda: (
                    load_vapid_subject(
                        self.config.agent.workspace_dir,
                    )
                    or loaded_keys.subject
                ),
                on_delivery_recorded=_on_delivery_recorded,
                on_subscription_expired=_on_subscription_expired,
                on_subscription_pruned=_on_subscription_pruned,
            )
            logger.info("web_push transport built (vapid keys loaded)")
        else:
            self._vapid_public_key = None
            self._web_push_transport = build_web_push_transport(
                private_key_pem=None,
                public_key_b64url=None,
                subject="mailto:operator@ds-agent.local",
            )
            logger.info(
                "web_push transport disabled",
                reason=getattr(loaded_keys, "reason", "unknown"),
            )

        self._dispatch_web_push_use_case = DispatchWebPushUseCase(
            transport=self._web_push_transport,
            subscription_store=self._web_push_subscription_store,
        )

        self._refresh_connector_registry()

    # -- Public facade: keep existing API surface stable ----------------------

    @property
    def config(self) -> Any:
        """Direct config access (preserves existing route/handler API)."""
        return self._config_manager.config

    @property
    def config_manager(self) -> Any:
        """Access the underlying ConfigManager for advanced operations."""
        return self._config_manager

    @property
    def oauth_service(self) -> Any:
        """Access the OAuth service for login/status/disconnect."""
        return self._oauth_service

    @property
    def token_store(self) -> Any:
        """Access the auth profile token store."""
        return self._token_store

    @property
    def transcript_store(self) -> Any:
        """Access the transcript store for session history queries."""
        return self._transcript_store

    @property
    def checkpoint_store(self) -> Any:
        """Access the checkpoint store for in-progress state queries."""
        return self._checkpoint_store

    @property
    def result_card_store(self) -> Any:
        """Access the persisted result-card store."""
        return self._result_card_store

    @property
    def approval_store(self) -> Any:
        """Access the persisted approval store."""
        return self._approval_store

    @property
    def approval_grant_store(self) -> Any:
        """Access the persisted approval grant store (W2-F)."""
        return self._approval_grant_store

    @property
    def policy_store(self) -> Any:
        """Access the persisted autonomous policy store."""
        return self._policy_store

    @property
    def access_policy_store(self) -> Any:
        """Access the resource sharing policy store (PLAN_05)."""
        return self._access_policy_store

    @property
    def access_log_store(self) -> Any:
        """Access the redacted access-audit log store (PLAN_05)."""
        return self._access_log_store

    @property
    def resource_access_guard(self) -> Any:
        """Access the resource boundary middleware (PLAN_05)."""
        return self._resource_access_guard

    @property
    def web_push_subscription_store(self) -> Any:
        """Access the per-operator web push subscription store (W4-06b)."""
        return self._web_push_subscription_store

    @property
    def web_push_subject_store(self) -> Any:
        """Access the persisted VAPID subject store."""
        return self._web_push_subject_store

    @property
    def web_push_metrics_store(self) -> Any:
        """Access the per-operator web push metrics store."""
        return self._web_push_metrics_store

    @property
    def web_push_transport(self) -> Any:
        """Access the web push transport adapter (real or no-op)."""
        return self._web_push_transport

    @property
    def dispatch_web_push_use_case(self) -> Any:
        """Access the use case that fans out push notifications."""
        return self._dispatch_web_push_use_case

    @property
    def vapid_public_key(self) -> str | None:
        """Return the VAPID public key string or ``None`` when missing."""
        return self._vapid_public_key

    @property
    def vapid_subject(self) -> str | None:
        """Return the effective VAPID subject from persisted config or env."""
        return (
            self._web_push_subject_store.load()
            or os.environ.get(
                "DS_AGENT_VAPID_SUBJECT",
                "",
            ).strip()
            or None
        )

    @property
    def promoted_artifact_store(self) -> Any:
        """Access the persisted promoted-artifact store (Plan 03 §1.1)."""
        return self._promoted_artifact_store

    @property
    def organization_store(self) -> Any:
        """Access the persisted organization store."""
        return self._organization_store

    @property
    def skill_hub(self) -> Any:
        """Access the shared skill hub."""
        return self._skill_hub

    def semantic_lookup_metric(
        self,
        query: str,
        *,
        grain: str | None = None,
    ) -> dict[str, object]:
        container = self._get_semantic_memory_container()
        result = container.resolve_metric.execute(query, grain=grain)
        glossary = container.lookup_term.execute(query, limit=5)
        payload = result.model_dump(mode="json")
        payload["glossaryMatches"] = [term.model_dump(mode="json") for term in glossary.matches]
        return payload

    def semantic_get_trust(
        self,
        fqtns: list[str],
        *,
        allow_untrusted: bool = False,
    ) -> dict[str, object]:
        return (
            self._get_semantic_memory_container()
            .check_table_trust.execute(
                fqtns,
                allow_untrusted=allow_untrusted,
            )
            .model_dump(mode="json")
        )

    def semantic_get_verified_query(
        self,
        metric_id: str,
        *,
        dialect: str = "postgres",
        bindings: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return (
            self._get_semantic_memory_container()
            .find_verified_query.execute(
                metric_id,
                dialect=dialect,
                bindings=bindings,
            )
            .model_dump(mode="json")
        )

    def semantic_load_pack(
        self,
        *,
        pack_dir: str | None,
        skill_name: str | None,
        dry_run: bool = True,
        allow_definition_updates: bool = False,
    ) -> dict[str, object]:
        from ds_agent.memory.semantic.infrastructure.pack_paths import resolve_semantic_pack_dir

        resolved_pack_dir, source = resolve_semantic_pack_dir(
            pack_dir=pack_dir,
            skill_name=skill_name,
            workspace_dir=self.config.agent.workspace_dir,
        )
        payload = (
            self._get_semantic_memory_container()
            .load_semantic_pack.execute(
                str(resolved_pack_dir),
                dry_run=dry_run,
                allow_definition_updates=allow_definition_updates,
            )
            .model_dump(mode="json")
        )
        payload["resolvedPackDir"] = str(resolved_pack_dir)
        payload["source"] = source
        if skill_name is not None:
            payload["skillName"] = skill_name
        return payload

    def semantic_list_snapshots(self, *, limit: int = 20) -> list[dict[str, object]]:
        return [
            snapshot.model_dump(mode="json")
            for snapshot in self._get_semantic_memory_container().list_semantic_snapshots.execute(
                limit=limit
            )
        ]

    def semantic_restore_snapshot(self, *, snapshot_id: str) -> dict[str, object]:
        return (
            self._get_semantic_memory_container()
            .restore_semantic_snapshot.execute(snapshot_id)
            .model_dump(mode="json")
        )

    def semantic_sync_source(
        self,
        *,
        source_kind: str,
        connector_name: str | None = None,
        endpoint: str | None = None,
        token: str | None = None,
        token_env: str | None = None,
        source_name: str | None = None,
        owner: str | None = None,
        dry_run: bool = True,
        overwrite: bool = False,
        id_namespace: str | None = None,
        since: str | None = None,
        allowed_grades: list[str] | None = None,
    ) -> dict[str, object]:
        from datetime import datetime

        from ds_agent.memory.semantic.application.ports import SemanticSyncPolicy
        from ds_agent.memory.semantic.domain.trust import TrustGrade
        from ds_agent.memory.semantic.infrastructure.adapters import (
            BigQuerySchemaAdapter,
            DbtMetricFlowAdapter,
            LookerAdapter,
            PostgresSchemaAdapter,
            SnowflakeSchemaAdapter,
            UnityCatalogAdapter,
        )

        normalized_kind = source_kind.strip().lower().replace("-", "_")
        if normalized_kind in {"postgres", "bigquery", "snowflake"}:
            normalized_connector_name = str(connector_name or "").strip()
            if not normalized_connector_name:
                raise ValueError(f"connectorName is required for {normalized_kind} sync")
            connector_settings = self.config.connectors.get(normalized_connector_name)
            if connector_settings is None:
                raise ValueError(f"Unknown connector: {normalized_connector_name}")
            connector = connector_settings.to_domain(normalized_connector_name)
            if connector.type.value != normalized_kind:
                raise ValueError(
                    f"semantic sync {normalized_kind} requires a {normalized_kind} connector"
                )
            warehouse_adapter = self._connector_adapter_factory(connector)
            if normalized_kind == "postgres":
                source = PostgresSchemaAdapter(
                    connector,
                    warehouse_adapter,
                    owner=owner,
                )
            elif normalized_kind == "bigquery":
                source = BigQuerySchemaAdapter(
                    connector,
                    warehouse_adapter,
                    owner=owner,
                )
            else:
                source = SnowflakeSchemaAdapter(
                    connector,
                    warehouse_adapter,
                    owner=owner,
                )
            effective_source_name = source_name or normalized_connector_name
        elif normalized_kind == "dbt":
            resolved_endpoint = str(
                endpoint or os.environ.get("DS_AGENT_DBT_METRICFLOW_ENDPOINT") or ""
            ).strip()
            if not resolved_endpoint:
                raise ValueError("dbt sync requires endpoint or DS_AGENT_DBT_METRICFLOW_ENDPOINT")
            resolved_token = str(token or "").strip()
            if not resolved_token and token_env:
                resolved_token = os.environ.get(token_env, "")
            if not resolved_token:
                resolved_token = os.environ.get("DS_AGENT_DBT_METRICFLOW_TOKEN", "")

            effective_source_name = source_name or "dbt_metricflow"
            source = DbtMetricFlowAdapter(
                resolved_endpoint,
                auth_token=resolved_token or None,
                source_name=effective_source_name,
                owner=owner or "dbt_metricflow",
            )
        elif normalized_kind == "unity_catalog":
            resolved_endpoint = str(
                endpoint or os.environ.get("DS_AGENT_UNITY_CATALOG_ENDPOINT") or ""
            ).strip()
            if not resolved_endpoint:
                raise ValueError(
                    "unity_catalog sync requires endpoint or DS_AGENT_UNITY_CATALOG_ENDPOINT"
                )
            resolved_token = str(token or "").strip()
            if not resolved_token and token_env:
                resolved_token = os.environ.get(token_env, "")
            if not resolved_token:
                resolved_token = os.environ.get("DS_AGENT_UNITY_CATALOG_TOKEN", "")

            effective_source_name = source_name or "unity_catalog"
            source = UnityCatalogAdapter(
                resolved_endpoint,
                auth_token=resolved_token or None,
                source_name=effective_source_name,
                owner=owner or "unity_catalog",
            )
        elif normalized_kind == "looker":
            resolved_endpoint = str(
                endpoint or os.environ.get("DS_AGENT_LOOKER_ENDPOINT") or ""
            ).strip()
            if not resolved_endpoint:
                raise ValueError("looker sync requires endpoint or DS_AGENT_LOOKER_ENDPOINT")
            resolved_token = str(token or "").strip()
            if not resolved_token and token_env:
                resolved_token = os.environ.get(token_env, "")
            if not resolved_token:
                resolved_token = os.environ.get("DS_AGENT_LOOKER_TOKEN", "")

            effective_source_name = source_name or "looker"
            source = LookerAdapter(
                resolved_endpoint,
                auth_token=resolved_token or None,
                source_name=effective_source_name,
                owner=owner or "looker",
            )
        else:
            raise ValueError(
                "sourceKind must be one of: postgres, bigquery, snowflake, dbt, "
                "unity_catalog, looker"
            )

        resolved_since = None
        if since:
            try:
                resolved_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("since must be an ISO-8601 datetime") from exc

        resolved_allowed_grades = (
            [TrustGrade(value) for value in allowed_grades]
            if allowed_grades
            else [TrustGrade.GOLD, TrustGrade.SILVER]
        )
        effective_namespace = id_namespace
        if effective_namespace is None:
            if normalized_kind == "dbt":
                effective_namespace = "dbt:"
            elif normalized_kind == "unity_catalog":
                effective_namespace = "unity:"
            elif normalized_kind == "looker":
                effective_namespace = "looker:"
        return (
            self._get_semantic_memory_container()
            .sync_semantic_source.execute(
                source,
                policy=SemanticSyncPolicy(
                    source_name=effective_source_name,
                    overwrite=overwrite,
                    id_namespace=effective_namespace,
                    allowed_grades=resolved_allowed_grades,
                ),
                since=resolved_since,
                dry_run=dry_run,
            )
            .model_dump(mode="json")
        )

    def _get_semantic_memory_container(self) -> Any:
        from ds_agent.infrastructure.semantic_memory_container import (
            build_semantic_memory_container,
        )

        if self._semantic_memory_container is None:
            self._semantic_memory_container = build_semantic_memory_container(
                workspace_dir=self.config.agent.workspace_dir
            )
        return self._semantic_memory_container

    def _get_decision_os_container(self) -> Any:
        from ds_agent.infrastructure.decision_os_container import build_decision_os_container

        if self._decision_os_container is None:
            self._decision_os_container = build_decision_os_container(
                self.config.agent.workspace_dir,
                runtime_event_log=self._runtime_event_log,
            )
        return self._decision_os_container

    def decision_os_overview(
        self,
        *,
        run_limit: int = 20,
        model_limit: int = 20,
        decision_limit: int = 20,
    ) -> dict[str, object]:
        container = self._get_decision_os_container()
        runs = sorted(
            container.experiment_log.list_runs(limit=max(run_limit, 1)),
            key=lambda item: item.created_at,
            reverse=True,
        )
        models = sorted(
            container.model_registry.list_models(limit=max(model_limit, 1)),
            key=lambda item: (item.created_at, item.version),
            reverse=True,
        )

        decisions_by_id: dict[str, object] = {}
        for model in models:
            for decision in container.promotion_decisions.list_for_model(
                model.model_id,
                limit=max(decision_limit, 1),
            ):
                decisions_by_id.setdefault(decision.decision_id, decision)
        decisions = sorted(
            decisions_by_id.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )[: max(decision_limit, 1)]

        monitor_states = []
        for model in models:
            state = container.deploy_monitor_states.latest(model.model_id)
            if state is not None:
                monitor_states.append(state)
        monitor_states.sort(key=lambda item: item.observed_at, reverse=True)

        return {
            "summary": {
                "runCount": len(runs),
                "modelCount": len(models),
                "decisionCount": len(decisions),
                "monitorStateCount": len(monitor_states),
            },
            "runs": [run.model_dump(mode="json") for run in runs],
            "models": [model.model_dump(mode="json") for model in models],
            "promotionDecisions": [decision.model_dump(mode="json") for decision in decisions],
            "monitorStates": [state.model_dump(mode="json") for state in monitor_states],
        }

    def decision_os_compare_runs(self, *, run_a_id: str, run_b_id: str) -> dict[str, object]:
        container = self._get_decision_os_container()
        return container.compare_runs.execute(run_a_id, run_b_id).model_dump(mode="json")

    def decision_os_request_promotion(
        self,
        *,
        candidate_run_id: str,
        target_stage: str,
        approvers: list[str],
        rollback_plan_ref: str,
    ) -> dict[str, object]:
        container = self._get_decision_os_container()
        result = container.request_promotion.execute(
            candidate_run_id=candidate_run_id,
            target_stage=target_stage,
            approvers=approvers,
            rollback_plan_ref=rollback_plan_ref,
        )
        self.record_runtime_event(
            category="deployment",
            kind="decision_os.promotion_requested",
            severity="info",
            message=(f"Decision OS promotion requested for {candidate_run_id} to {target_stage}."),
            session_id="decision_os:review",
            surface="ws",
            source="decision_os",
            metadata={
                "decisionId": result.decision_id,
                "candidateRunId": candidate_run_id,
                "targetStage": target_stage,
                "chainState": result.chain_state,
            },
        )
        return result.model_dump(mode="json")

    def decision_os_resolve_promotion(
        self,
        *,
        decision_id: str,
        decision: str,
        approver: str,
        note: str = "",
    ) -> dict[str, object]:
        container = self._get_decision_os_container()
        if decision == "approved":
            result = container.approve_promotion.execute(
                decision_id=decision_id,
                approver=approver,
                note=note,
            )
            message = (
                f"Decision OS promotion {decision_id} approved by {approver} "
                f"({result.chain_state})."
            )
            severity = "info"
        elif decision == "rejected":
            result = container.reject_promotion.execute(
                decision_id=decision_id,
                approver=approver,
                reason=note,
            )
            message = f"Decision OS promotion {decision_id} rejected by {approver}."
            severity = "warning"
        else:
            raise ValueError("decision must be 'approved' or 'rejected'")

        self.record_runtime_event(
            category="deployment",
            kind="decision_os.promotion_resolved",
            severity=severity,
            message=message,
            session_id="decision_os:review",
            surface="ws",
            source="decision_os",
            metadata={
                "decisionId": result.decision_id,
                "candidateRunId": result.candidate_run_id,
                "candidateModelId": result.candidate_model_id,
                "decision": decision,
                "approver": approver,
                "chainState": result.chain_state,
            },
        )
        return result.model_dump(mode="json")

    def decision_os_apply_promotion(self, *, decision_id: str) -> dict[str, object]:
        container = self._get_decision_os_container()
        result = container.apply_promotion.execute(decision_id=decision_id)
        self.record_runtime_event(
            category="deployment",
            kind="decision_os.promotion_applied",
            severity="info",
            message=(
                f"Decision OS promotion {decision_id} applied as {result.applied_alias} "
                f"for {result.candidate_model_id}."
            ),
            session_id="decision_os:review",
            surface="ws",
            source="decision_os",
            metadata=result.model_dump(mode="json"),
        )
        return result.model_dump(mode="json")

    def decision_os_get_post_deploy_status(
        self,
        *,
        model_id: str,
        window: str = "7d",
    ) -> dict[str, object]:
        container = self._get_decision_os_container()
        return container.get_post_deploy_status.execute(
            model_id=model_id,
            window=window,
        ).model_dump(mode="json")

    def get_org_snapshot(self, *, actor_id: str = _DEFAULT_ORG_ACTOR) -> dict[str, object]:
        """Return organization settings and usage summary for admin surfaces."""
        self._require_org_admin(actor_id)
        start_ts, end_ts = self._organization_store.month_range()
        organization = self._organization_store.get()
        return {
            "organization": self._serialize_organization(organization),
            "usage": self._organization_store.get_usage_summary(start_ts=start_ts, end_ts=end_ts),
        }

    def get_usage_summary(
        self,
        *,
        actor_id: str = _DEFAULT_ORG_ACTOR,
        session_id: str | None = None,
    ) -> dict[str, object]:
        """Return the current cost-governance usage summary."""
        summary = self._usage_summary_service.get_summary(
            actor_id=actor_id,
            monthly_budget_usd=self.config.provider.max_budget_usd,
            warning_threshold_pct=self.config.provider.budget_warning_threshold_pct,
            current_session_id=session_id,
        )
        return summary.to_payload()

    def update_org_settings(
        self,
        *,
        actor_id: str,
        settings: dict[str, object],
    ) -> dict[str, object]:
        """Update organization settings and return the latest snapshot."""
        from ds_agent.runtime.organization_store import UNSET as ORG_UNSET

        self._require_org_admin(actor_id)
        allowed_providers = settings.get("allowedProviders", ORG_UNSET)
        max_budget_usd_per_user = (
            _optional_float(settings.get("maxBudgetUsdPerUser"))
            if "maxBudgetUsdPerUser" in settings
            else ORG_UNSET
        )
        max_budget_usd_per_org = (
            _optional_float(settings.get("maxBudgetUsdPerOrg"))
            if "maxBudgetUsdPerOrg" in settings
            else ORG_UNSET
        )
        external_data_transfer_allowed = (
            _optional_bool(settings.get("externalDataTransferAllowed"))
            if "externalDataTransferAllowed" in settings
            else ORG_UNSET
        )
        export_allowed = (
            _optional_bool(settings.get("exportAllowed"))
            if "exportAllowed" in settings
            else ORG_UNSET
        )
        connector_creation_allowed = (
            _optional_bool(settings.get("connectorCreationAllowed"))
            if "connectorCreationAllowed" in settings
            else ORG_UNSET
        )
        org = self._organization_store.update_settings(
            allowed_providers=(
                [str(item) for item in allowed_providers if isinstance(item, str)]
                if isinstance(allowed_providers, list)
                else ORG_UNSET
            ),
            max_budget_usd_per_user=max_budget_usd_per_user,
            max_budget_usd_per_org=max_budget_usd_per_org,
            external_data_transfer_allowed=external_data_transfer_allowed,
            export_allowed=export_allowed,
            connector_creation_allowed=connector_creation_allowed,
        )
        start_ts, end_ts = self._organization_store.month_range()
        return {
            "organization": self._serialize_organization(org),
            "usage": self._organization_store.get_usage_summary(start_ts=start_ts, end_ts=end_ts),
        }

    def invite_org_member(
        self,
        *,
        actor_id: str,
        user_id: str,
        role: str,
        display_name: str | None = None,
    ) -> dict[str, object]:
        """Add or update one member."""
        self._require_org_admin(actor_id)
        org = self._organization_store.invite_member(
            user_id,
            role=_parse_org_role(role),
            display_name=display_name,
        )
        return {"organization": self._serialize_organization(org)}

    def update_org_member_role(
        self,
        *,
        actor_id: str,
        user_id: str,
        role: str,
    ) -> dict[str, object]:
        """Update one member role."""
        self._require_org_admin(actor_id)
        org = self._organization_store.update_member_role(user_id, _parse_org_role(role))
        return {"organization": self._serialize_organization(org)}

    def export_audit_log(
        self,
        *,
        actor_id: str,
        start_date: str,
        end_date: str,
        format: str,
    ) -> dict[str, object]:
        """Export audit log records as CSV or JSONL."""
        from datetime import datetime

        self._require_org_admin(actor_id)
        start_ts = (
            datetime.fromisoformat(start_date)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        end_ts = (
            datetime.fromisoformat(end_date)
            .replace(hour=23, minute=59, second=59, microsecond=999999)
            .timestamp()
        )
        records = self._load_audit_records(start_ts=start_ts, end_ts=end_ts)
        if format == "jsonl":
            content = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
            content_type = "application/x-ndjson"
        else:
            output = io.StringIO()
            fieldnames = sorted({key for record in records for key in record})
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(record)
            content = output.getvalue()
            content_type = "text/csv"
        return {
            "filename": f"audit-log-{start_date}-to-{end_date}.{format}",
            "content": content,
            "contentType": content_type,
            "recordCount": len(records),
        }

    def list_manageable_skills(self) -> list[dict]:
        """Return custom skills for the settings UI."""
        return self._skill_hub.list_manageable_skills()

    def get_custom_skill(self, name: str) -> dict | None:
        """Return one custom skill with editable markdown body."""
        skill = self._skill_hub.view_skill(name)
        if skill is None:
            return None
        if skill.get("sourceKind") != "custom":
            return None
        return skill

    def save_custom_skill(
        self,
        *,
        name: str,
        description: str,
        content: str,
        category: str = "custom",
        tags: object | None = None,
        tools: object | None = None,
        permissions: object | None = None,
        enabled: bool = True,
        existing_name: str | None = None,
    ) -> dict:
        """Create or update one custom skill."""
        return self._skill_hub.save_custom_skill(
            name=name,
            description=description,
            content=content,
            category=category,
            tags=[str(item) for item in tags] if isinstance(tags, list) else [],
            tools=[str(item) for item in tools] if isinstance(tools, list) else [],
            permissions=permissions if isinstance(permissions, dict) else {},
            enabled=enabled,
            existing_name=existing_name,
        )

    def import_custom_skill(self, raw_markdown: str) -> dict:
        """Import one raw markdown skill."""
        return self._skill_hub.import_custom_skill(raw_markdown)

    def import_custom_skill_from_url(self, url: str) -> dict:
        """Fetch and import one remote markdown skill."""
        return self.import_custom_skill(_fetch_remote_skill_markdown(url))

    def delete_custom_skill(self, name: str) -> bool:
        """Delete one custom skill."""
        return self._skill_hub.delete_custom_skill(name)

    def set_skill_enabled(self, name: str, enabled: bool) -> dict:
        """Toggle one custom skill enabled state."""
        return self._skill_hub.set_skill_enabled(name, enabled)

    def register_runtime_listener(self, listener: Callable[[str, dict], None]) -> None:
        """Register one listener for runtime alert broadcasts."""
        self._runtime_event_listeners.add(listener)

    def unregister_runtime_listener(self, listener: Callable[[str, dict], None]) -> None:
        """Remove a previously registered runtime alert listener."""
        self._runtime_event_listeners.discard(listener)

    def record_runtime_event(
        self,
        *,
        category: str,
        kind: str,
        severity: str,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "daemon",
        source: str = "runtime",
        metadata: dict[str, object] | None = None,
        created_at: float | None = None,
    ) -> object:
        """Append one runtime event and broadcast it to connected operators."""
        event = self._runtime_event_log.record(
            category=category,
            kind=kind,
            severity=severity,
            message=message,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            source=source,
            metadata=metadata,
            created_at=created_at,
        )
        payload = _serialize_runtime_event_record(event)
        for listener in list(self._runtime_event_listeners):
            try:
                listener("runtime.alert", payload)
            except Exception as exc:
                logger.warning("runtime_event_listener_failed", error=str(exc))
        return event

    def list_runtime_events(
        self,
        *,
        limit: int = 50,
        session_id: str | None = None,
        category: str | None = None,
    ) -> list:
        """Return recent runtime events for operator surfaces."""
        return self._runtime_event_log.list(
            limit=limit,
            session_id=session_id,
            category=category,
        )

    async def get_or_create_agent(
        self,
        session_id: str,
        callbacks: WsAgentCallbacks,
        model: str | None = None,
    ) -> DSAgent:
        return await self._sessions.get_or_create(session_id, callbacks, model)

    def get_agent(self, session_id: str) -> DSAgent | None:
        return self._sessions.get(session_id)

    def broadcast_mission_context_update(
        self,
        session_id: str,
        *,
        delta: dict[str, object] | None = None,
    ) -> None:
        """Broadcast a mission.context.updated event to every active listener.

        Used after task contract / pause actions where the mission context
        derives from store state independent of an active agent run.

        ``delta`` carries the changed-only subset of (``dataSources``,
        ``deliverables``, ``constraints``) so renderers can patch incrementally
        without paying the cost of a full snapshot diff. Unknown delta keys are
        ignored.
        """

        if not session_id:
            return
        try:
            mission = self.get_mission_context(session_id)
        except Exception as exc:
            logger.warning("mission_broadcast_build_failed", error=str(exc))
            return
        payload: dict[str, object] = {
            "sessionId": session_id,
            **mission.model_dump(mode="json", by_alias=True),
        }
        if delta:
            allowed = {"dataSources", "deliverables", "constraints"}
            scoped = {k: v for k, v in delta.items() if k in allowed}
            if scoped:
                payload["delta"] = scoped
        for listener in list(self._runtime_event_listeners):
            try:
                listener("mission.context.updated", payload)
            except Exception as exc:
                logger.warning("mission_broadcast_listener_failed", error=str(exc))

    def get_mission_context(
        self,
        session_id: str,
        *,
        latest_run: RunState | None = None,
        active_agent: object | None = None,
    ) -> object:
        from ds_agent.application.usecases.get_mission_context_usecase import (
            GetMissionContextUseCase,
        )
        from ds_agent.infrastructure.persistence.task_contract_store import (
            SqliteTaskContractStore,
        )
        from ds_agent.runtime.goal_store import JsonGoalStore

        workspace_dir = self.config.agent.workspace_dir
        task_store = SqliteTaskContractStore.for_workspace(workspace_dir)
        goal_store = JsonGoalStore(workspace_dir)

        active_bundle = task_store.get_active_bundle(session_id)
        active_goal = goal_store.get_active_goal(session_id)
        resolved_run = latest_run
        if resolved_run is None:
            running_runs = self.list_runs(
                session_id=session_id, status=RuntimeStatus.RUNNING, limit=1
            )
            resolved_run = running_runs[0] if running_runs else None
        if resolved_run is None:
            latest_runs = self.list_runs(session_id=session_id, limit=1)
            resolved_run = latest_runs[0] if latest_runs else None

        return GetMissionContextUseCase(self.config).execute(
            session_id=session_id,
            task_contract_bundle=active_bundle,
            active_goal=active_goal,
            latest_run=resolved_run,
            active_agent=active_agent if active_agent is not None else self.get_agent(session_id),
        )

    def get_session_history(self, session_id: str, limit: int = 50) -> list:
        checkpoint = self._checkpoint_store.load(session_id)
        if checkpoint is not None:
            return checkpoint.messages[-limit:]
        return self._transcript_store.load_messages(session_id, limit=limit)

    def get_session_result_cards(self, session_id: str, limit: int = 100) -> list[object]:
        return self._result_card_store.list_cards_by_session(session_id, limit=limit)

    def get_status(self) -> dict:
        overlay = self._get_effective_authority_overlay()
        status = self._sessions.get_status()
        status["activeRuns"] = self._runs.active_count
        status["activeTasks"] = self._task_ledger.active_count
        status["pendingApprovals"] = self._approval_store.pending_count
        status["autonomousRuntimeEnabled"] = bool(
            getattr(self.config.gateway, "autonomous_runtime_enabled", False)
        )
        status["autonomousRuntimeRunning"] = self.background_runtime_running
        status["sensorBacklog"] = self.sensor_backlog
        status["recoveredSessions"] = self.recovered_sessions
        status["automationProfile"] = self.automation_profile
        status["recurringGoalCount"] = len(self._policy_store.list_recurring_goals())
        status["standingOrderCount"] = len(self._policy_store.get_standing_orders()) + len(
            self._policy_store.list_standing_order_records()
        )
        status["resourcePressure"] = self.resource_pressure
        status["authorityOverlay"] = None if overlay.mode is None else overlay.mode.value
        status["authorityOverlayStartedAt"] = (
            None if overlay.started_at is None else overlay.started_at.isoformat()
        )
        status["authorityOverlayExpiresAt"] = (
            None if overlay.expires_at is None else overlay.expires_at.isoformat()
        )
        status["effectiveAuthorityMode"] = effective_authority_mode(
            legacy_mode=self.config.agent.mode,
            overlay_mode=getattr(self.config.gateway, "authority_overlay", None),
            overlay_started_at=getattr(self.config.gateway, "authority_overlay_started_at", None),
        ).value
        return status

    def list_connectors(self, *, actor_id: str = _DEFAULT_ORG_ACTOR) -> dict[str, object]:
        return {
            "connectors": [
                self._serialize_connector(name, settings)
                for name, settings in sorted(self.config.connectors.items())
            ],
            "connectorCreationAllowed": self._connector_creation_allowed(actor_id=actor_id),
        }

    def test_connector(
        self,
        params: dict[str, object],
        *,
        actor_id: str = _DEFAULT_ORG_ACTOR,
    ) -> dict[str, object]:
        if not self._connector_creation_allowed(actor_id=actor_id):
            raise ValueError("Connector creation is disabled by organization policy.")

        settings, name, credential_payload = self._connector_settings_from_payload(params)
        effective_payload = credential_payload
        existing = self.config.connectors.get(name)
        probe_settings = settings

        if settings.credential_method.value == "secret_manager" and effective_payload is None:
            if (
                existing is not None
                and existing.credential_method == settings.credential_method
                and existing.credential_ref
                and self._connector_secrets.has_secret(existing.credential_ref)
            ):
                effective_payload = self._connector_secrets.load(existing.credential_ref)
                probe_settings = self._connector_settings_model(
                    type=settings.type,
                    label=settings.label,
                    options=dict(settings.options),
                    credential_method=settings.credential_method,
                    credential_ref=existing.credential_ref,
                    read_only=settings.read_only,
                    timeout_seconds=settings.timeout_seconds,
                    max_rows=settings.max_rows,
                )
            else:
                raise ValueError(
                    "credentialPayload is required when testing a secret-manager connector"
                )

        self._validate_connector_settings(settings, name, effective_payload)
        probe_credential_ref: str | None = None
        if (
            settings.credential_method.value == "secret_manager"
            and credential_payload
            and probe_settings is settings
        ):
            probe_credential_ref = self._connector_secrets.store(
                f"{name}__probe__",
                credential_payload,
            )
            probe_settings = self._connector_settings_model(
                type=settings.type,
                label=settings.label,
                options=dict(settings.options),
                credential_method=settings.credential_method,
                credential_ref=probe_credential_ref,
                read_only=settings.read_only,
                timeout_seconds=settings.timeout_seconds,
                max_rows=settings.max_rows,
            )
        connector = probe_settings.to_domain(name)
        probe_started = time.perf_counter()
        try:
            adapter = self._connector_adapter_factory(connector)
            adapter.execute_query(
                QuerySpec(
                    sql=self._connector_probe_sql(connector.type),
                    connector_name=name,
                    timeout_override=probe_settings.timeout_seconds,
                )
            )
        except Exception as exc:
            presentation = present_rpc_exception("connector.test", exc)
            return {
                "ok": False,
                "errorCode": presentation.catalog_code,
                "message": presentation.message,
                "details": {
                    **self._connector_target_details(connector),
                    "technicalMessage": presentation.technical_message or str(exc),
                },
                "warnings": presentation.warnings,
            }
        finally:
            if probe_credential_ref:
                self._connector_secrets.delete(probe_credential_ref)

        return {
            "ok": True,
            "latencyMs": int((time.perf_counter() - probe_started) * 1000),
            "probe": {
                "kind": "select_1",
                "message": "Read-only probe succeeded.",
            },
            "details": self._connector_target_details(connector),
            "warnings": [],
        }

    def save_connector(
        self,
        params: dict[str, object],
        *,
        actor_id: str = _DEFAULT_ORG_ACTOR,
    ) -> dict[str, object]:
        if not self._connector_creation_allowed(actor_id=actor_id):
            raise ValueError("Connector creation is disabled by organization policy.")

        settings, name, credential_payload = self._connector_settings_from_payload(params)
        existing = self.config.connectors.get(name)
        credential_ref = settings.credential_ref
        effective_payload = credential_payload

        if settings.credential_method.value == "secret_manager":
            if credential_payload is not None:
                effective_payload = credential_payload
            elif (
                existing is not None
                and existing.credential_method == settings.credential_method
                and existing.credential_ref
                and self._connector_secrets.has_secret(existing.credential_ref)
            ):
                credential_ref = existing.credential_ref
                effective_payload = self._connector_secrets.load(existing.credential_ref)
            else:
                raise ValueError("credentialPayload is required for secret-manager connectors")

        self._validate_connector_settings(settings, name, effective_payload)

        if settings.credential_method.value == "secret_manager" and credential_payload is not None:
            credential_ref = self._connector_secrets.store(name, credential_payload)

        persisted = self._connector_settings_model(
            type=settings.type,
            label=settings.label or name,
            options=dict(settings.options),
            credential_method=settings.credential_method,
            credential_ref=credential_ref,
            read_only=settings.read_only,
            timeout_seconds=settings.timeout_seconds,
            max_rows=settings.max_rows,
        )
        self._config_manager.upsert_connector(name, persisted)
        self._refresh_connector_registry()
        return {"connector": self._serialize_connector(name, persisted)}

    def delete_connector(
        self,
        name: str,
        *,
        actor_id: str = _DEFAULT_ORG_ACTOR,
    ) -> dict[str, object]:
        if not self._connector_creation_allowed(actor_id=actor_id):
            raise ValueError("Connector creation is disabled by organization policy.")

        removed = self._config_manager.delete_connector(name)
        if removed is None:
            return {"deleted": False}
        if removed.credential_method.value == "secret_manager" and removed.credential_ref:
            self._connector_secrets.delete(removed.credential_ref)
        self._refresh_connector_registry()
        return {"deleted": True}

    def _require_org_admin(self, actor_id: str) -> None:
        if self._organization_store.is_admin(actor_id):
            return
        raise ValueError("Organization admin access is required")

    @staticmethod
    def _serialize_organization(organization: object) -> dict[str, object]:
        members = [
            {
                "userId": getattr(member, "user_id", ""),
                "role": getattr(getattr(member, "role", None), "value", "viewer"),
                "displayName": getattr(member, "display_name", None),
                "invitedAt": getattr(member, "invited_at", 0.0),
            }
            for member in getattr(organization, "members", [])
        ]
        settings = getattr(organization, "settings", None)
        return {
            "id": getattr(organization, "id", ""),
            "name": getattr(organization, "name", ""),
            "members": members,
            "settings": {
                "allowedProviders": list(getattr(settings, "allowed_providers", []) or []),
                "maxBudgetUsdPerUser": getattr(settings, "max_budget_usd_per_user", None),
                "maxBudgetUsdPerOrg": getattr(settings, "max_budget_usd_per_org", None),
                "externalDataTransferAllowed": bool(
                    getattr(settings, "external_data_transfer_allowed", True)
                ),
                "exportAllowed": bool(getattr(settings, "export_allowed", True)),
                "connectorCreationAllowed": bool(
                    getattr(settings, "connector_creation_allowed", True)
                ),
            },
            "createdAt": getattr(organization, "created_at", 0.0),
            "updatedAt": getattr(organization, "updated_at", 0.0),
        }

    def _load_audit_records(
        self,
        *,
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> list[dict[str, object]]:
        audit_path = get_runtime_storage_root(self.config.agent.workspace_dir) / "audit_log.jsonl"
        if not audit_path.exists():
            return []
        records: list[dict[str, object]] = []
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            timestamp = float(record.get("timestamp", 0.0))
            if start_ts is not None and timestamp < start_ts:
                continue
            if end_ts is not None and timestamp > end_ts:
                continue
            records.append(record)
        records.sort(key=lambda item: float(item.get("timestamp", 0.0)), reverse=True)
        return records

    @property
    def background_runtime_running(self) -> bool:
        daemon = self._autonomous_daemon
        if daemon is None:
            return False
        return bool(getattr(daemon, "running", False))

    @property
    def sensor_backlog(self) -> int:
        daemon = self._autonomous_daemon
        if daemon is None:
            return 0
        backlog = getattr(daemon, "sensor_backlog", 0)
        return int(backlog)

    @property
    def recovered_sessions(self) -> int:
        daemon = self._autonomous_daemon
        if daemon is None:
            return 0
        recovered = getattr(daemon, "recovered_count", 0)
        return int(recovered)

    @property
    def automation_profile(self) -> str:
        daemon = self._autonomous_daemon
        if daemon is None:
            return str(self.config.gateway.automation_profile)
        profile = getattr(daemon, "automation_profile", self.config.gateway.automation_profile)
        return str(profile)

    @property
    def resource_pressure(self) -> bool:
        daemon = self._autonomous_daemon
        if daemon is None:
            return False
        return bool(getattr(daemon, "resource_pressure", False))

    async def start_background_runtime(self, force: bool = False) -> None:
        """Start the autonomous background runtime when enabled."""
        enabled = bool(getattr(self.config.gateway, "autonomous_runtime_enabled", False))
        if not (force or enabled):
            return
        if self._autonomous_daemon is None:
            from ds_agent.gateway.daemon import AutonomousDaemon

            self._autonomous_daemon = AutonomousDaemon(self)
        await self._autonomous_daemon.start()

    async def stop_background_runtime(self) -> None:
        """Stop the autonomous background runtime if it exists."""
        if self._autonomous_daemon is None:
            return
        await self._autonomous_daemon.stop()
        self._autonomous_daemon = None

    def publish_user_input_event(
        self,
        *,
        session_id: str,
        surface: str,
        message: str,
        run_id: str | None = None,
    ) -> None:
        """Forward foreground user input into the shared sensor hub."""
        daemon = self._autonomous_daemon
        if daemon is None:
            return
        publish = getattr(daemon, "publish_user_input", None)
        if callable(publish):
            publish(session_id=session_id, surface=surface, message=message, run_id=run_id)

    def get_run(self, run_id: str) -> RunState | None:
        """Return runtime state for a tracked run."""
        return self._runs.get(run_id)

    def _load_eval_task_and_run_for_runtime_run(self, run_id: str):
        """Rebuild the eval task/run pair for one tracked runtime run."""
        from ds_agent.evaluation.infrastructure.adapters.production_task_adapter import (
            ProductionTaskAdapter,
        )
        from ds_agent.evaluation.infrastructure.ingestion.session_trace_reader import (
            SessionTraceReader,
        )
        from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore

        runtime_run = self._runs.get(run_id)
        if runtime_run is None:
            raise ValueError(f"Unknown runId: {run_id}")

        workspace_dir = self.config.agent.workspace_dir
        trace_reader = SessionTraceReader.for_workspace(workspace_dir)
        run = trace_reader.read_session(
            session_id=runtime_run.session_id,
            task_id=runtime_run.task_id,
            run_id=runtime_run.run_id,
        )
        adapter = ProductionTaskAdapter()
        task_store = SqliteTaskContractStore.for_workspace(workspace_dir)
        bundle = (
            task_store.get_bundle(runtime_run.task_id)
            if runtime_run.task_id
            else task_store.get_active_bundle(runtime_run.session_id)
        )
        if bundle is None:
            task = adapter.from_session(
                session_id=runtime_run.session_id,
                prompt=run.user_prompt,
                task_id=runtime_run.task_id,
            )
        else:
            task = adapter.from_bundle(bundle)
            run = adapter.enrich_run(run, bundle)
        return runtime_run, trace_reader, task, run

    def _build_run_scorecard(
        self,
        *,
        run_id: str,
        task,
        run,
    ) -> dict[str, object]:
        from ds_agent.evaluation.application.use_cases.resolve_review_sampling import (
            ResolveReviewSampling,
        )
        from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
        from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
        from ds_agent.evaluation.infrastructure.persistence.jsonl_shadow_comparison_store import (
            JsonlShadowComparisonStore,
        )
        from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers
        from ds_agent.evaluation.presentation.electron_bridge.scorecard_payload import (
            build_run_scorecard_payload,
        )

        review_sampling: ReviewSamplingDecision | None = None
        runtime_run = self._runs.get(run_id)
        if (
            runtime_run is not None
            and runtime_run.status != RuntimeStatus.RUNNING
            and not runtime_run.surface.startswith("eval_")
        ):
            review_sampling = ResolveReviewSampling(self._review_sampling_store).execute(
                session_id=runtime_run.session_id,
                run_id=runtime_run.run_id,
                task_id=runtime_run.task_id or task.id,
                domain=task.domain,
                surface=runtime_run.surface,
                target_rate=_DEFAULT_REVIEW_SAMPLE_RATE,
            )
            run = _apply_review_sampling_metadata(run, review_sampling)

        report = ScoreRun(build_default_scorers()).execute(run=run, task=task)
        shadow_comparison = JsonlShadowComparisonStore.for_workspace(
            self.config.agent.workspace_dir
        ).latest_for_baseline_run(run_id)
        return build_run_scorecard_payload(
            report=report,
            run=run,
            task=task,
            review_sampling=review_sampling,
            shadow_comparison=shadow_comparison,
        )

    def get_run_scorecard(self, run_id: str) -> dict[str, object]:
        """Score one persisted runtime run and return a UI-friendly payload."""
        _, _, task, run = self._load_eval_task_and_run_for_runtime_run(run_id)
        return self._build_run_scorecard(run_id=run_id, task=task, run=run)

    def _load_eval_gold_tasks(self):
        from ds_agent.evaluation.infrastructure.gold_tasks.loader import GoldTaskLoader

        return GoldTaskLoader().load_suite(
            Path(__file__).resolve().parent.parent
            / "evaluation"
            / "infrastructure"
            / "gold_tasks"
            / "tasks"
        )

    def dispatch_regression_alerts(
        self,
        *,
        channels: Sequence[str] | None = None,
        mode: str | None = None,
        domain: str | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
        skip_if_unchanged: bool = False,
        dispatch_source: str = "runtime",
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "ws",
    ):
        """Dispatch regression-board alerts for the current evaluation dataset."""
        from ds_agent.evaluation.application.use_cases.build_regression_board import (
            BuildRegressionBoard,
        )
        from ds_agent.evaluation.application.use_cases.dispatch_regression_alerts import (
            DispatchRegressionAlerts,
        )
        from ds_agent.evaluation.infrastructure.alerting_adapter import (
            build_configured_regression_alert_notifiers,
        )
        from ds_agent.evaluation.infrastructure.persistence import (
            json_regression_alert_state_store,
        )
        from ds_agent.evaluation.infrastructure.persistence.json_regression_baseline_store import (
            JsonRegressionBaselineStore,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
            JsonlEvalDatasetStore,
        )

        tasks = self._load_eval_gold_tasks()
        report = DispatchRegressionAlerts(
            board_builder=BuildRegressionBoard(
                eval_store=JsonlEvalDatasetStore.for_workspace(self.config.agent.workspace_dir),
                baseline_store=JsonRegressionBaselineStore.for_workspace(
                    self.config.agent.workspace_dir
                ),
            ),
            notifiers=build_configured_regression_alert_notifiers(),
            state_store=json_regression_alert_state_store.JsonRegressionAlertStateStore.for_workspace(
                self.config.agent.workspace_dir
            ),
        ).execute(
            channels=channels,
            task_catalog=tasks,
            mode=mode,
            domain=domain,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
            skip_if_unchanged=skip_if_unchanged,
            dispatch_source=dispatch_source,
            dedupe_key=_regression_alert_dedupe_key(mode=mode, domain=domain),
        )
        if report.deliveries:
            self.record_runtime_event(
                category="evaluation",
                kind="regression_alert.dispatched",
                severity="warning",
                message=(
                    "Regression alerts dispatched for "
                    f"mode={mode or 'all'} domain={domain or 'all'}."
                ),
                session_id=session_id,
                run_id=run_id,
                surface=surface,
                source="evaluation_harness",
                metadata={
                    "dispatchSource": dispatch_source,
                    "channels": [delivery.channel for delivery in report.deliveries],
                    "alertCount": report.alert_count,
                    "deliveryCount": len(report.deliveries),
                    "fingerprint": report.fingerprint,
                    "mode": mode,
                    "domain": domain,
                },
            )
        return report

    def get_regression_board(
        self,
        mode: str | None = None,
        domain: str | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
    ) -> dict[str, object]:
        """Build the latest evaluation regression-board snapshot."""
        from ds_agent.evaluation.application.use_cases.build_regression_board import (
            BuildRegressionBoard,
        )
        from ds_agent.evaluation.infrastructure.persistence.json_regression_baseline_store import (
            JsonRegressionBaselineStore,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
            JsonlEvalDatasetStore,
        )
        from ds_agent.evaluation.presentation.electron_bridge.regression_payload import (
            build_regression_board_payload,
        )

        tasks = self._load_eval_gold_tasks()
        snapshot = BuildRegressionBoard(
            eval_store=JsonlEvalDatasetStore.for_workspace(self.config.agent.workspace_dir),
            baseline_store=JsonRegressionBaselineStore.for_workspace(
                self.config.agent.workspace_dir
            ),
        ).execute(
            task_catalog=tasks,
            mode=mode,
            domain=domain,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
        )
        return build_regression_board_payload(snapshot)

    def freeze_regression_baseline(
        self,
        commit_sha: str,
        mode: str | None = None,
        domain: str | None = None,
        recent_window: int = 3,
        baseline_window_days: int = 14,
        window_days: int | None = None,
    ) -> dict[str, object]:
        """Persist one frozen baseline and return the refreshed board payload."""
        from ds_agent.evaluation.application.use_cases.build_regression_board import (
            BuildRegressionBoard,
            FreezeRegressionBaseline,
        )
        from ds_agent.evaluation.infrastructure.persistence.json_regression_baseline_store import (
            JsonRegressionBaselineStore,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
            JsonlEvalDatasetStore,
        )
        from ds_agent.evaluation.presentation.electron_bridge.regression_payload import (
            build_regression_board_payload,
        )

        tasks = self._load_eval_gold_tasks()
        eval_store = JsonlEvalDatasetStore.for_workspace(self.config.agent.workspace_dir)
        baseline_store = JsonRegressionBaselineStore.for_workspace(self.config.agent.workspace_dir)
        baseline = FreezeRegressionBaseline(
            eval_store=eval_store,
            baseline_store=baseline_store,
        ).execute(
            commit_sha=commit_sha,
            axis="commit",
            task_catalog=tasks,
            mode=mode,
            domain=domain,
            window_days=window_days,
            baseline_window_days=baseline_window_days,
        )
        snapshot = BuildRegressionBoard(
            eval_store=eval_store,
            baseline_store=baseline_store,
        ).execute(
            task_catalog=tasks,
            mode=mode,
            domain=domain,
            recent_window=recent_window,
            baseline_window_days=baseline_window_days,
        )
        self.record_runtime_event(
            category="evaluation",
            kind="regression_alert.baseline_frozen",
            severity="info",
            message=(
                f"Regression baseline frozen for mode={mode or 'all'} domain={domain or 'all'}."
            ),
            session_id="evaluation:regression_alerts",
            surface="ws",
            source="evaluation_harness",
            metadata={
                "baselineId": baseline.baseline_id,
                "commitSha": baseline.commit_sha,
                "mode": mode,
                "domain": domain,
                "windowDays": baseline.baseline_window_days,
            },
        )
        return {
            "baseline": baseline.model_dump(mode="json"),
            "board": build_regression_board_payload(snapshot),
        }

    def _maybe_dispatch_regression_alerts_for_task(
        self,
        *,
        runtime_run: RunState,
        domain: str | None,
        dispatch_source: str,
    ) -> None:
        """Best-effort regression-alert dispatch that never blocks the caller."""
        try:
            self.dispatch_regression_alerts(
                mode=None,
                domain=domain,
                skip_if_unchanged=True,
                dispatch_source=dispatch_source,
                session_id=runtime_run.session_id,
                run_id=runtime_run.run_id,
                surface=runtime_run.surface,
            )
        except Exception as exc:
            logger.warning(
                "regression_alert_dispatch_failed",
                run_id=runtime_run.run_id,
                source=dispatch_source,
                error=str(exc),
            )
            self.record_runtime_event(
                category="evaluation",
                kind="regression_alert.failed",
                severity="error",
                message=(
                    "Automatic regression-alert dispatch failed for "
                    f"mode=all domain={domain or 'all'}."
                ),
                session_id=runtime_run.session_id,
                run_id=runtime_run.run_id,
                surface=runtime_run.surface,
                source="evaluation_harness",
                metadata={
                    "dispatchSource": dispatch_source,
                    "mode": None,
                    "domain": domain,
                    "error": str(exc),
                },
            )

    def submit_run_human_rubric(
        self,
        run_id: str,
        reviewer_id: str,
        dimensions: dict[str, float],
        comment: str | None = None,
    ) -> dict[str, object]:
        """Persist one human rubric review for a runtime run and return the new scorecard."""
        from ds_agent.evaluation.application.use_cases.ingest_human_rubric import (
            IngestHumanRubric,
        )
        from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric
        from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
            JsonlEvalDatasetStore,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_human_rubric_store import (
            JsonlHumanRubricStore,
        )
        from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers

        runtime_run, trace_reader, task, run = self._load_eval_task_and_run_for_runtime_run(run_id)
        use_case = IngestHumanRubric(
            trace_reader=trace_reader,
            rubric_store=JsonlHumanRubricStore.for_workspace(self.config.agent.workspace_dir),
            scorers=build_default_scorers(),
            eval_store=JsonlEvalDatasetStore.for_workspace(self.config.agent.workspace_dir),
        )
        use_case.execute(
            session_id=runtime_run.session_id,
            task=task,
            task_id=runtime_run.task_id,
            run_id=runtime_run.run_id,
            run=run,
            rubric=HumanRubric(
                reviewer_id=reviewer_id,
                dimensions=dimensions,
                comment=comment,
            ),
        )
        self._maybe_dispatch_regression_alerts_for_task(
            runtime_run=runtime_run,
            domain=task.domain,
            dispatch_source="runtime",
        )
        _, _, task, refreshed_run = self._load_eval_task_and_run_for_runtime_run(run_id)
        return self._build_run_scorecard(run_id=run_id, task=task, run=refreshed_run)

    def run_shadow_compare(
        self,
        run_id: str,
        model: str | None = None,
        shadow_factor: float = 0.5,
    ) -> dict[str, object]:
        """Execute one shadow twin for a tracked run and return the refreshed scorecard."""
        from ds_agent.evaluation.application.use_cases.run_shadow_comparison import (
            RunShadowComparison,
        )
        from ds_agent.evaluation.infrastructure.orchestrator.agent_eval_orchestrator import (
            AgentEvalOrchestrator,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
            JsonlEvalDatasetStore,
        )
        from ds_agent.evaluation.infrastructure.persistence.jsonl_shadow_comparison_store import (
            JsonlShadowComparisonStore,
        )
        from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers
        from ds_agent.runtime.provider_factory import create_provider_router

        runtime_run, trace_reader, task, run = self._load_eval_task_and_run_for_runtime_run(run_id)
        selected_model = str(model or self.config.provider.default_model)

        def provider_factory(model_name: str):
            return create_provider_router(
                model_name,
                self.config,
                token_store=self._token_store,
            )

        use_case = RunShadowComparison(
            trace_reader=trace_reader,
            shadow_orchestrator=AgentEvalOrchestrator(
                workspace_dir=self.config.agent.workspace_dir,
                provider_factory=provider_factory,
                model_name=selected_model,
                run_mode="shadow",
                budget_factor=shadow_factor,
                session_registry=self._runtime_sessions,
                run_registry=self._runs,
                runtime_event_log=self._runtime_event_log,
                organization_store=self._organization_store,
                transcript_store=self._transcript_store,
                checkpoint_store=self._checkpoint_store,
                goal_store=self._goal_store,
                approval_store=self._approval_store,
                task_ledger=self._task_ledger,
            ),
            scorers=build_default_scorers(),
            comparison_store=JsonlShadowComparisonStore.for_workspace(
                self.config.agent.workspace_dir
            ),
            eval_store=JsonlEvalDatasetStore.for_workspace(self.config.agent.workspace_dir),
            shadow_model=selected_model,
            shadow_budget_factor=shadow_factor,
        )
        use_case.execute(
            session_id=runtime_run.session_id,
            task=task,
            task_id=runtime_run.task_id,
            run_id=runtime_run.run_id,
            baseline_run=run,
        )
        self._maybe_dispatch_regression_alerts_for_task(
            runtime_run=runtime_run,
            domain=task.domain,
            dispatch_source="runtime",
        )
        return self._build_run_scorecard(run_id=run_id, task=task, run=run)

    def list_runs(
        self,
        *,
        session_id: str | None = None,
        status: RuntimeStatus | None = None,
        limit: int = 20,
    ) -> list[RunState]:
        """List tracked runs ordered by recency."""
        return self._runs.list(session_id=session_id, status=status, limit=limit)

    def list_sessions(self, *, limit: int = 20) -> list[RuntimeSession]:
        """List runtime-visible sessions ordered by recency."""
        return self._runtime_sessions.list(limit=limit)

    def list_tasks(
        self,
        *,
        run_id: str | None = None,
        status: RuntimeStatus | None = None,
        limit: int = 20,
    ) -> list[TaskState]:
        """List tracked tasks ordered by recency."""
        return self._task_ledger.list(run_id=run_id, status=status, limit=limit)

    def list_approvals(
        self,
        *,
        session_id: str | None = None,
        status: ApprovalStatus | None = None,
        limit: int = 20,
    ) -> list:
        """List persisted approvals ordered by recency."""
        return self._approval_store.list(session_id=session_id, status=status, limit=limit)

    def get_approval_request(self, approval_id: str) -> Any:
        """Return one approval request enriched for the approval modal."""
        from ds_agent.application.use_cases.get_approval_request_usecase import (
            GetApprovalRequestUseCase,
        )

        return GetApprovalRequestUseCase(self._approval_store).execute(approval_id)

    def submit_approval(self, request: dict[str, object]) -> Any:
        """Submit one approval decision using the v2 approval contract."""
        from ds_agent.application.use_cases.submit_approval_usecase import SubmitApprovalUseCase

        result = SubmitApprovalUseCase(self._approval_store).execute(request)
        approval = result.approval
        if approval is None:
            return result

        finalized = self._finalize_resolved_approval(
            approval=approval,
            status=approval.status,
            source=approval.source,
            actor=approval.actor,
        )
        result.approval = finalized
        result.metadata = dict(getattr(finalized, "metadata", {}) or {})
        result.response = getattr(finalized, "response", result.response)
        result.status = getattr(getattr(finalized, "status", None), "value", result.status)

        if (
            result.decision == "allow"
            and result.scope in ("session", "workspace")
            and finalized is not None
        ):
            try:
                self._issue_approval_grant_for(approval=finalized, scope=result.scope)
            except Exception as exc:  # pragma: no cover - defensive: grant issuance is best-effort
                logger.warning(
                    "approval_grant_issue_failed",
                    approval_id=getattr(finalized, "approval_id", None),
                    error=str(exc),
                )
        return result

    def _issue_approval_grant_for(self, *, approval: object, scope: str) -> None:
        """Persist a grant after the approval submit flow records the decision."""
        from ds_agent.application.use_cases.approval_grant_usecases import (
            IssueApprovalGrantInput,
            IssueApprovalGrantUseCase,
        )
        from ds_agent.application.use_cases.get_approval_request_usecase import (
            GetApprovalRequestUseCase,
        )
        from ds_agent.domain.entities.approval_grant import ApprovalGrantScope

        try:
            view = GetApprovalRequestUseCase(self._approval_store).execute(approval)
        except ValueError:
            return

        scope_enum = (
            ApprovalGrantScope.SESSION if scope == "session" else ApprovalGrantScope.WORKSPACE
        )
        workspace_id = view.workspace_id or str(self.config.agent.workspace_dir)
        affected_scopes = list(view.affected_scopes) if view.affected_scopes else []

        IssueApprovalGrantUseCase(self._approval_grant_store).execute(
            IssueApprovalGrantInput(
                approval_id=view.approval_id,
                scope=scope_enum,
                risk_code=view.risk_code or view.kind or "GENERIC",
                kind=view.kind,
                session_id=view.session_id,
                workspace_id=workspace_id,
                actor=view.actor,
                source=view.source,
                affected_scopes=affected_scopes,
            )
        )

    def resolve_approval(
        self,
        approval_id: str,
        *,
        status: ApprovalStatus,
        response: str | None = None,
        source: str | None = None,
        actor: str | None = None,
    ) -> object | None:
        """Resolve one persisted approval request."""
        approval = self._approval_store.resolve(
            approval_id,
            status=status,
            response=response,
            source=source,
            actor=actor,
        )
        if approval is None:
            return None

        return self._finalize_resolved_approval(
            approval=approval,
            status=status,
            source=source,
            actor=actor,
        )

    def _finalize_resolved_approval(
        self,
        *,
        approval: object,
        status: ApprovalStatus,
        source: str | None,
        actor: str | None,
    ) -> object:
        """Apply approval side effects that must run after persistence."""
        if getattr(approval, "kind", "generic") != "semantic_proposal":
            return approval

        reviewer = (actor or source or "operator").strip() or "operator"
        outcome = resolve_semantic_proposal_approval(
            approval,
            workspace_dir=self.config.agent.workspace_dir,
            reviewer=reviewer,
        )
        metadata = dict(getattr(approval, "metadata", {}) or {})
        metadata["semanticProposalOutcome"] = {
            "proposalId": outcome.proposal_id,
            "proposalStatus": outcome.proposal_status,
            "action": outcome.action,
            "applied": outcome.applied,
            "appliedTarget": outcome.applied_target,
        }
        approval.metadata = metadata
        self._approval_store.replace(approval)
        self.record_runtime_event(
            category="approval",
            kind=("semantic.proposal.applied" if outcome.applied else "semantic.proposal.reviewed"),
            severity="success" if status == ApprovalStatus.APPROVED else "warning",
            message=(
                f"Semantic proposal {outcome.action}d: {outcome.proposal_id}"
                if outcome.action != "apply"
                else f"Semantic proposal applied: {outcome.proposal_id}"
            ),
            session_id=approval.session_id,
            run_id=approval.run_id,
            surface=approval.surface,
            source="approval_bus",
            metadata=metadata,
        )
        return approval

    def list_recurring_goals(self) -> list:
        """List configured recurring autonomous goals."""
        return self._policy_store.list_recurring_goals()

    def upsert_recurring_goal(
        self,
        *,
        session_id: str,
        prompt: str,
        interval_seconds: float,
        enabled: bool = True,
        goal_id: str | None = None,
    ) -> object:
        """Create or update a recurring autonomous goal."""
        return self._policy_store.upsert_recurring_goal(
            session_id=session_id,
            prompt=prompt,
            interval_seconds=interval_seconds,
            enabled=enabled,
            goal_id=goal_id,
        )

    def get_standing_orders(self) -> list[str]:
        """Return standing autonomous policy orders."""
        return self._policy_store.get_standing_orders()

    def set_standing_orders(self, orders: list[str]) -> None:
        """Replace standing autonomous policy orders."""
        self._policy_store.set_standing_orders(orders)

    def get_action_matrix_overrides(self) -> dict[str, dict[str, str]]:
        """Return persisted authority x action-class matrix overrides."""

        return self._policy_store.get_action_matrix_overrides()

    def set_action_matrix_overrides(
        self,
        overrides: dict[str, dict[str, str]],
    ) -> dict[str, dict[str, str]]:
        """Replace persisted authority x action-class matrix overrides."""

        return self._policy_store.set_action_matrix_overrides(overrides)

    def build_action_matrix(self) -> ActionMatrix:
        """Return the effective action matrix with persisted overrides applied."""

        return self._policy_store.build_action_matrix()

    async def start_run(
        self,
        *,
        session_id: str,
        message: str,
        callbacks: AgentCallbacks,
        model: str | None = None,
        surface: str = "ws",
        actor_id: str | None = None,
        resume_from_checkpoint: bool = False,
        branched_from_run_id: str | None = None,
        rerun_from_node_id: str | None = None,
    ) -> RunState:
        """Start one tracked agent run for the given session.

        When ``resume_from_checkpoint`` is true and a persisted checkpoint exists for
        ``session_id``, the agent resumes from the checkpointed history instead of
        starting a fresh transcript. If no checkpoint is available, the run starts
        normally and ``RunState.resumed_from_checkpoint`` is left ``False``.
        """
        existing = self._runs.latest_for_session(
            session_id,
            statuses={RuntimeStatus.RUNNING},
        )
        if existing is not None:
            await self.abort_run(run_id=existing.run_id)
            await self.wait_for_run(existing.run_id, timeout_ms=1000)

        selected_model = str(model or self.config.provider.default_model)
        resolved_actor_id = self._resolve_org_actor_id(
            session_id=session_id,
            surface=surface,
            actor_id=actor_id,
        )
        violation = self._org_policy_gate.check_run_allowed(
            model_name=selected_model,
            actor_id=resolved_actor_id,
            organization=self._organization_store.get(),
            usage_store=self._organization_store,
        )
        if violation is not None:
            raise ValueError(violation)
        usage_before = self._usage_summary_service.get_summary(
            actor_id=resolved_actor_id,
            monthly_budget_usd=self.config.provider.max_budget_usd,
            warning_threshold_pct=self.config.provider.budget_warning_threshold_pct,
            current_session_id=session_id,
        )
        if usage_before.limit_exceeded:
            raise ValueError(
                "Monthly budget exceeded "
                f"({usage_before.monthly_cost_usd:.2f} / "
                f"{self.config.provider.max_budget_usd:.2f} USD). "
                "Increase the limit in Settings before starting a new analysis."
            )

        self._runtime_sessions.ensure(session_id, surface)
        agent = await self._sessions.get_or_create(session_id, callbacks, model)
        if hasattr(agent, "set_runtime_context"):
            agent.set_runtime_context(run_id=None, surface=surface)

        resume_checkpoint = None
        if resume_from_checkpoint and self._checkpoint_store is not None:
            try:
                resume_checkpoint = self._checkpoint_store.load(session_id)
            except Exception:
                logger.exception("checkpoint_load_failed", session_id=session_id)
                resume_checkpoint = None

        run = self._runs.create(
            session_id,
            surface,
            message,
            parent_run_id=branched_from_run_id,
        )
        run.resumed_from_checkpoint = resume_checkpoint is not None
        if rerun_from_node_id is not None:
            run.rerun_from_node_id = rerun_from_node_id
        if hasattr(agent, "set_runtime_context"):
            agent.set_runtime_context(run.run_id, surface=surface)

        async def _execute() -> None:
            execution_mode = "background" if surface == "daemon" else "interactive"
            run_kwargs: dict[str, object] = {}
            if execution_mode == "background":
                run_kwargs["execution_mode"] = execution_mode
                budget_policy = self._build_autonomous_run_budget(agent)
                if budget_policy is not None:
                    run_kwargs["budget_policy"] = budget_policy
            if resume_checkpoint is not None:
                run_kwargs["resume_from_checkpoint"] = resume_checkpoint

            self.record_runtime_event(
                category="task",
                kind="task.started",
                severity="info",
                message=(
                    "Autonomous background task started."
                    if execution_mode == "background"
                    else "Interactive task started."
                ),
                session_id=session_id,
                run_id=run.run_id,
                surface=surface,
                source="agent",
                metadata={
                    "executionMode": execution_mode,
                    "message": message,
                    "model": selected_model,
                },
            )

            try:
                result = (
                    await agent.run(message, **run_kwargs)
                    if run_kwargs
                    else await agent.run(message)
                )
                cost = 0.0
                budget_summary: dict[str, object] = {}
                if hasattr(agent, "_budget"):
                    cost = agent._budget.state.total_cost_usd
                    get_summary = getattr(agent._budget, "get_summary", None)
                    if callable(get_summary):
                        budget_summary = get_summary()
                completed_run = self._runs.mark_succeeded(run.run_id, result=result, cost_usd=cost)
                self._organization_store.record_usage(
                    actor_id=resolved_actor_id,
                    provider=_provider_name_from_model(selected_model),
                    cost_usd=cost,
                    model=selected_model,
                    session_id=session_id,
                    run_id=run.run_id,
                    input_tokens=int(budget_summary.get("input_tokens", 0) or 0),
                    output_tokens=int(budget_summary.get("output_tokens", 0) or 0),
                    cache_read_tokens=int(budget_summary.get("cache_read_tokens", 0) or 0),
                    cache_write_tokens=int(budget_summary.get("cache_write_tokens", 0) or 0),
                    reasoning_tokens=int(budget_summary.get("reasoning_tokens", 0) or 0),
                    cache_savings_usd=float(budget_summary.get("cache_savings_usd", 0.0) or 0.0),
                )
                self._emit_usage_summary_event(
                    callbacks=callbacks,
                    actor_id=resolved_actor_id,
                    session_id=session_id,
                    previous_warning_level=usage_before.warning_level,
                )
                self.record_runtime_event(
                    category="task",
                    kind="task.completed",
                    severity="success",
                    message=(
                        "Autonomous background task completed."
                        if execution_mode == "background"
                        else "Interactive task completed."
                    ),
                    session_id=session_id,
                    run_id=run.run_id,
                    surface=surface,
                    source="agent",
                    metadata={
                        "executionMode": execution_mode,
                        "costUsd": cost,
                        "budgetLimitUsd": (
                            None
                            if "budget_policy" not in run_kwargs
                            else getattr(run_kwargs["budget_policy"], "max_cost_usd", None)
                        ),
                    },
                )
                self._emit_mission_context_event(
                    callbacks=callbacks,
                    session_id=session_id,
                    latest_run=completed_run,
                    active_agent=agent,
                )
                emit_stream_done = getattr(callbacks, "emit_stream_done", None)
                if callable(emit_stream_done):
                    message_id = getattr(agent, "last_assistant_message_id", None)
                    result_cards = getattr(agent, "last_result_cards", None)
                    cards_payload = (
                        _serialize_result_cards(result_cards)
                        if isinstance(result_cards, list)
                        else None
                    )
                    await emit_stream_done(
                        result,
                        cost,
                        message_id=message_id if isinstance(message_id, str) else None,
                        cards=cards_payload or None,
                    )
            except asyncio.CancelledError:
                cancelled_run = self._runs.mark_cancelled(run.run_id)
                self.record_runtime_event(
                    category="task",
                    kind="task.cancelled",
                    severity="warning",
                    message=(
                        "Autonomous background task was cancelled."
                        if execution_mode == "background"
                        else "Interactive task was cancelled."
                    ),
                    session_id=session_id,
                    run_id=run.run_id,
                    surface=surface,
                    source="agent",
                    metadata={"executionMode": execution_mode},
                )
                self._emit_mission_context_event(
                    callbacks=callbacks,
                    session_id=session_id,
                    latest_run=cancelled_run,
                    active_agent=agent,
                )
                emit_stream_done = getattr(callbacks, "emit_stream_done", None)
                if callable(emit_stream_done):
                    await emit_stream_done("[Aborted]", 0.0)
                raise
            except Exception as exc:
                logger.error("agent_run_error", run_id=run.run_id, error=str(exc), exc_info=True)
                cost = 0.0
                budget_summary = {}
                if hasattr(agent, "_budget"):
                    cost = agent._budget.state.total_cost_usd
                    get_summary = getattr(agent._budget, "get_summary", None)
                    if callable(get_summary):
                        budget_summary = get_summary()
                self._organization_store.record_usage(
                    actor_id=resolved_actor_id,
                    provider=_provider_name_from_model(selected_model),
                    cost_usd=cost,
                    model=selected_model,
                    session_id=session_id,
                    run_id=run.run_id,
                    input_tokens=int(budget_summary.get("input_tokens", 0) or 0),
                    output_tokens=int(budget_summary.get("output_tokens", 0) or 0),
                    cache_read_tokens=int(budget_summary.get("cache_read_tokens", 0) or 0),
                    cache_write_tokens=int(budget_summary.get("cache_write_tokens", 0) or 0),
                    reasoning_tokens=int(budget_summary.get("reasoning_tokens", 0) or 0),
                    cache_savings_usd=float(budget_summary.get("cache_savings_usd", 0.0) or 0.0),
                )
                self._emit_usage_summary_event(
                    callbacks=callbacks,
                    actor_id=resolved_actor_id,
                    session_id=session_id,
                    previous_warning_level=usage_before.warning_level,
                )
                failed_run = self._runs.mark_failed(run.run_id, str(exc))
                self.record_runtime_event(
                    category="task",
                    kind="task.failed",
                    severity="error",
                    message=(
                        "Autonomous background task failed."
                        if execution_mode == "background"
                        else "Interactive task failed."
                    ),
                    session_id=session_id,
                    run_id=run.run_id,
                    surface=surface,
                    source="agent",
                    metadata={
                        "executionMode": execution_mode,
                        "error": str(exc),
                    },
                )
                self._emit_mission_context_event(
                    callbacks=callbacks,
                    session_id=session_id,
                    latest_run=failed_run,
                    active_agent=agent,
                )
                emit_stream_done = getattr(callbacks, "emit_stream_done", None)
                if callable(emit_stream_done):
                    await emit_stream_done("Internal server error", 0.0)
            finally:
                self._runtime_sessions.bind_run(session_id, run.run_id, surface)

        task = asyncio.create_task(_execute(), name=f"run:{run.run_id}")
        task_state = self._task_ledger.register(run.run_id, task)
        updated = self._runs.attach_task(run.run_id, task_state.task_id)
        self._runtime_sessions.bind_run(session_id, run.run_id, surface)
        self._emit_mission_context_event(
            callbacks=callbacks,
            session_id=session_id,
            latest_run=updated or run,
            active_agent=agent,
        )
        return updated or run

    def _build_autonomous_run_budget(self, agent: object) -> BudgetPolicy | None:
        limit = float(getattr(self.config.gateway, "autonomous_budget_per_run_usd", 0.0))
        if limit <= 0:
            return None

        budget = getattr(agent, "_budget", None)
        policy = getattr(budget, "policy", None)
        if not isinstance(policy, BudgetPolicy):
            return None
        return replace(policy, max_cost_usd=limit)

    async def wait_for_run(self, run_id: str, timeout_ms: int | None = None) -> RunState | None:
        """Wait for a run's backing task and return its latest state."""
        timeout_seconds = None if timeout_ms is None else max(float(timeout_ms) / 1000.0, 0.0)
        await self._task_ledger.wait_for_run(run_id, timeout_seconds=timeout_seconds)
        return self._runs.get(run_id)

    async def abort_run(
        self,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
    ) -> RunState | None:
        """Abort a run by explicit run id or by latest active session run."""
        target_run_id = run_id
        if target_run_id is None and session_id is not None:
            active = self._runs.latest_for_session(
                session_id,
                statuses={RuntimeStatus.RUNNING},
            )
            target_run_id = None if active is None else active.run_id

        if target_run_id is None:
            return None

        task = self._task_ledger.get_task_for_run(target_run_id)
        run = self._runs.get(target_run_id)
        if task is None or task.done():
            return run

        self._task_ledger.cancel_for_run(target_run_id)
        await asyncio.sleep(0)
        return self._runs.get(target_run_id) or run

    def set_config(self, path: str, value: object) -> None:
        self._config_manager.set(path, value)
        if path == "gateway.authority_overlay":
            if value == "incident":
                self._config_manager.set(
                    "gateway.authority_overlay_started_at",
                    new_incident_started_at(),
                )
            else:
                self._config_manager.set("gateway.authority_overlay_started_at", None)
        if path.startswith("observability."):
            configure_backend_observability(self.config)
        if path == "agent.workspace_dir":
            from ds_agent.api.agent_session_registry import AgentSessionRegistry
            from ds_agent.api.workspace_service import WorkspaceService
            from ds_agent.application.services.usage_summary import UsageSummaryService
            from ds_agent.runtime.approval_grant_store import JsonApprovalGrantStore
            from ds_agent.runtime.approval_store import JsonApprovalStore
            from ds_agent.runtime.checkpoint_store import JsonCheckpointStore
            from ds_agent.runtime.organization_store import JsonOrganizationStore
            from ds_agent.runtime.policy_store import JsonPolicyStore
            from ds_agent.runtime.run_registry import RunRegistry
            from ds_agent.runtime.runtime_event_log import RuntimeEventLog
            from ds_agent.runtime.session_registry import RuntimeSessionRegistry
            from ds_agent.runtime.task_ledger import TaskLedger
            from ds_agent.runtime.transcript_store import JsonTranscriptStore

            self._workspace = WorkspaceService(str(self.config.agent.workspace_dir))
            self._transcript_store = JsonTranscriptStore(self.config.agent.workspace_dir)
            self._checkpoint_store = JsonCheckpointStore(self.config.agent.workspace_dir)
            self._approval_store = JsonApprovalStore(self.config.agent.workspace_dir)
            self._approval_grant_store = JsonApprovalGrantStore(self.config.agent.workspace_dir)
            self._organization_store = JsonOrganizationStore(self.config.agent.workspace_dir)
            self._usage_summary_service = UsageSummaryService(self._organization_store)
            self._policy_store = JsonPolicyStore(self.config.agent.workspace_dir)
            self._runtime_event_log = RuntimeEventLog(self.config.agent.workspace_dir)
            self._sessions = AgentSessionRegistry(
                self.config,
                token_store=self._token_store,
                transcript_store=self._transcript_store,
                checkpoint_store=self._checkpoint_store,
                approval_store=self._approval_store,
                skill_hub=self._skill_hub,
                org_policy_supplier=self._organization_store.get,
            )
            self._runtime_sessions = RuntimeSessionRegistry(self.config.agent.workspace_dir)
            self._task_ledger = TaskLedger(self.config.agent.workspace_dir)
            self._runs = RunRegistry(self._runtime_sessions, self.config.agent.workspace_dir)
            self._semantic_memory_container = None
            self._decision_os_container = None
            self._refresh_connector_registry()

    def _get_effective_authority_overlay(self):
        overlay = resolve_authority_overlay(
            getattr(self.config.gateway, "authority_overlay", None),
            getattr(self.config.gateway, "authority_overlay_started_at", None),
        )
        if not overlay.expired:
            return overlay

        self._config_manager.set("gateway.authority_overlay", None)
        self._config_manager.set("gateway.authority_overlay_started_at", None)
        self.record_runtime_event(
            category="policy",
            kind="policy.authority_overlay_expired",
            severity="info",
            message="Incident authority overlay expired and was cleared automatically.",
            surface="daemon",
            source="autonomy_control_plane",
            metadata={
                "expiredAt": (
                    None if overlay.expires_at is None else overlay.expires_at.isoformat()
                ),
            },
        )
        return resolve_authority_overlay(None, None)

    def _emit_usage_summary_event(
        self,
        *,
        callbacks: AgentCallbacks,
        actor_id: str,
        session_id: str | None,
        previous_warning_level: str,
    ) -> None:
        emit_event = getattr(callbacks, "emit_event", None)
        if not callable(emit_event):
            return
        summary = self.get_usage_summary(actor_id=actor_id, session_id=session_id)
        emit_event("usage.summary", summary)
        warning_level = str(summary.get("warningLevel", "ok"))
        if warning_level not in {"warning", "exhausted"} or warning_level == previous_warning_level:
            return
        budget_used_pct = float(summary.get("budgetUsedPct", 0.0) or 0.0)
        monthly_budget = summary.get("monthlyBudgetUsd")
        monthly_budget_text = (
            f"${float(monthly_budget):.2f}"
            if monthly_budget is not None
            else "the configured monthly budget"
        )
        emit_event(
            "budget.warning",
            {
                "dimension": "cost",
                "level": "exhausted" if warning_level == "exhausted" else "warning",
                "pct": budget_used_pct,
                "message": (
                    "Monthly AI budget reached. "
                    f"You have used {budget_used_pct:.0f}% of {monthly_budget_text}."
                    if warning_level == "exhausted"
                    else "Monthly AI budget warning. "
                    f"You have used {budget_used_pct:.0f}% of {monthly_budget_text}."
                ),
            },
        )

    def _emit_mission_context_event(
        self,
        *,
        callbacks: AgentCallbacks,
        session_id: str,
        latest_run: RunState | None = None,
        active_agent: object | None = None,
    ) -> None:
        emit_event = getattr(callbacks, "emit_event", None)
        if not callable(emit_event):
            return
        mission = self.get_mission_context(
            session_id,
            latest_run=latest_run,
            active_agent=active_agent,
        )
        emit_event(
            "mission.context.updated",
            {
                "sessionId": session_id,
                **mission.model_dump(mode="json", by_alias=True),
            },
        )

    def _resolve_org_actor_id(
        self,
        *,
        session_id: str,
        surface: str,
        actor_id: str | None,
    ) -> str:
        explicit = (actor_id or "").strip()
        if explicit:
            return explicit
        if surface == "daemon":
            return "autonomous-daemon"
        if session_id.startswith("telegram:"):
            conversation_id, _thread_id = parse_telegram_session_id(session_id)
            return f"telegram:{conversation_id}"
        return _DEFAULT_ORG_ACTOR

    def _refresh_connector_registry(self) -> None:
        from ds_agent.application.services.warehouse_service import set_warehouse_adapters
        from ds_agent.infrastructure.persistence.connector_factory import create_connector_adapters

        set_warehouse_adapters(
            create_connector_adapters(
                {
                    name: settings.to_domain(name)
                    for name, settings in self.config.connectors.items()
                }
            )
        )

    def _connector_creation_allowed(self, *, actor_id: str) -> bool:
        _ = actor_id
        organization = self._organization_store.get()
        settings = getattr(organization, "settings", None)
        return bool(getattr(settings, "connector_creation_allowed", True))

    def _connector_settings_from_payload(
        self,
        payload: dict[str, object],
    ) -> tuple[object, str, dict[str, object] | None]:
        name = _normalize_connector_name(payload.get("name"))
        options = payload.get("options")
        credential_payload = payload.get("credentialPayload")
        settings = self._connector_settings_model(
            type=payload.get("type"),
            label=str(payload.get("label", "")).strip(),
            options=options if isinstance(options, dict) else {},
            credential_method=payload.get(
                "credentialMethod",
                payload.get("credential_method", "env"),
            ),
            credential_ref=str(
                payload.get("credentialRef", payload.get("credential_ref", "")) or ""
            ).strip(),
            read_only=bool(payload.get("readOnly", payload.get("read_only", True))),
            timeout_seconds=int(
                payload.get("timeoutSeconds", payload.get("timeout_seconds", 30)) or 30
            ),
            max_rows=int(payload.get("maxRows", payload.get("max_rows", 10_000)) or 10_000),
        )
        return (
            settings,
            name,
            credential_payload if isinstance(credential_payload, dict) else None,
        )

    def _serialize_connector(self, name: str, settings: object) -> dict[str, object]:
        credential_method = getattr(settings, "credential_method", "env")
        credential_ref = str(getattr(settings, "credential_ref", "") or "")
        method_name = getattr(credential_method, "value", credential_method)
        has_credential = (
            self._connector_secrets.has_secret(credential_ref)
            if method_name == "secret_manager"
            else bool(credential_ref)
        )
        connector_type = getattr(
            getattr(settings, "type", None),
            "value",
            getattr(settings, "type", ""),
        )
        return {
            "name": name,
            "type": connector_type,
            "label": getattr(settings, "label", name) or name,
            "credentialMethod": method_name,
            "credentialRef": credential_ref,
            "hasCredential": has_credential,
            "readOnly": bool(getattr(settings, "read_only", True)),
            "timeoutSeconds": int(getattr(settings, "timeout_seconds", 30)),
            "maxRows": int(getattr(settings, "max_rows", 10_000)),
            "options": dict(getattr(settings, "options", {}) or {}),
        }

    def _validate_connector_settings(
        self,
        settings: object,
        name: str,
        credential_payload: dict[str, object] | None,
    ) -> None:
        connector = settings.to_domain(name)
        if not connector.read_only:
            raise ValueError("Connectors must remain read-only.")

        connector_type = getattr(connector.type, "value", str(connector.type))
        if connector_type == "postgres":
            self._validate_postgres_connector(connector, credential_payload)
            return
        if connector_type == "bigquery":
            self._validate_bigquery_connector(connector, credential_payload)
            return
        if connector_type == "snowflake":
            self._validate_snowflake_connector(connector, credential_payload)
            return

    @staticmethod
    def _validate_postgres_connector(
        connector: object,
        credential_payload: dict[str, object] | None,
    ) -> None:
        get_str_option = connector.get_str_option
        if not get_str_option("host"):
            raise ValueError("Postgres connectors require options.host")
        if not get_str_option("database"):
            raise ValueError("Postgres connectors require options.database")

        if credential_payload is None:
            return
        kind = str(credential_payload.get("kind", "") or "")
        if kind not in {"password", "dsn"}:
            raise ValueError("Postgres secret payload kind must be 'password' or 'dsn'")

    @staticmethod
    def _validate_bigquery_connector(
        connector: object,
        credential_payload: dict[str, object] | None,
    ) -> None:
        get_str_option = connector.get_str_option
        if not get_str_option("project_id"):
            raise ValueError("BigQuery connectors require options.project_id")

        if credential_payload is None:
            return

        kind = str(credential_payload.get("kind", "") or "")
        if kind == "oauth_ref":
            ref = str(credential_payload.get("ref", "") or "").strip()
            if not ref:
                raise ValueError("BigQuery oauth_ref payload requires ref")
            return
        if kind != "service_account_json":
            raise ValueError(
                "BigQuery secret payload kind must be 'service_account_json' or 'oauth_ref'"
            )

        json_text = credential_payload.get("json")
        info = credential_payload.get("info")
        if isinstance(json_text, str) and json_text.strip():
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError as exc:
                raise ValueError("BigQuery service account JSON is invalid") from exc
            if not isinstance(parsed, dict):
                raise ValueError("BigQuery service account JSON must decode to an object")
            return
        if isinstance(info, dict) and info:
            return
        raise ValueError("BigQuery service account payload requires json or info")

    @staticmethod
    def _validate_snowflake_connector(
        connector: object,
        credential_payload: dict[str, object] | None,
    ) -> None:
        get_str_option = connector.get_str_option
        required_fields = {
            "account": get_str_option("account", aliases=("host",)),
            "warehouse": get_str_option("warehouse"),
            "database": get_str_option("database"),
            "username": get_str_option("username"),
        }
        for field_name, value in required_fields.items():
            if not value:
                raise ValueError(f"Snowflake connectors require options.{field_name}")

        if credential_payload is None:
            return
        kind = str(credential_payload.get("kind", "") or "")
        if kind != "password":
            raise ValueError("Snowflake secret payload kind must be 'password'")

    @staticmethod
    def _connector_probe_sql(_connector_type: object) -> str:
        return "SELECT 1"

    @staticmethod
    def _connector_target_details(connector: object) -> dict[str, object]:
        connector_type = getattr(
            getattr(connector, "type", None),
            "value",
            getattr(connector, "type", ""),
        )
        if connector_type == "postgres":
            return {
                "host": getattr(connector, "host", ""),
                "database": getattr(connector, "database", ""),
                "schema": getattr(connector, "schema", ""),
            }
        get_str_option = getattr(connector, "get_str_option", None)
        if callable(get_str_option) and connector_type == "bigquery":
            return {
                "projectId": get_str_option("project_id"),
                "dataset": get_str_option("dataset"),
                "location": get_str_option("location"),
            }
        if callable(get_str_option) and connector_type == "snowflake":
            return {
                "account": get_str_option("account", aliases=("host",)),
                "warehouse": get_str_option("warehouse"),
                "database": get_str_option("database"),
                "schema": get_str_option("schema", default="public"),
            }
        return {}

    def list_files(self, project_id: str | None = None) -> list[dict]:
        return self._workspace.list_files(project_id)

    def export_support_bundle(self, output_path: str) -> Path:
        """Create a redacted support bundle ZIP for the current workspace."""
        normalized = output_path.strip()
        if not normalized:
            raise ValueError("outputPath is required")

        from ds_agent.infrastructure.support.bundle_exporter import SupportBundleExporter

        exporter = SupportBundleExporter(
            config=self.config,
            safe_config=self.config_manager.get_dump(),
            status_snapshot=self.get_status(),
            config_path=self.config_manager.config_path,
        )
        return exporter.export(normalized)

    def delete_file(self, rel_path: str) -> dict:
        return self._workspace.delete_path(rel_path)

    def preview_file(
        self,
        rel_path: str,
        rows: int = 20,
        *,
        sheet_name: str | None = None,
        header_row: int = 1,
    ) -> dict:
        return self._workspace.preview_path(
            rel_path,
            rows=rows,
            sheet_name=sheet_name,
            header_row=header_row,
        )

    def export_file(
        self,
        rel_path: str,
        export_format: str,
        audience: str | None = None,
    ) -> dict:
        return self._workspace.export_path(
            rel_path,
            export_format,
            audience=audience,
        )

    def list_projects(self) -> list[dict]:
        return self._workspace.list_projects()

    def create_project(self, name: str, task_type: str | None = None) -> str:
        return self._workspace.create_project(name, task_type)


def _apply_review_sampling_metadata(run, review_sampling):
    metadata = dict(run.metadata)
    metadata["reviewSamplingSampled"] = review_sampling.sampled
    metadata["reviewSamplingTargetRate"] = review_sampling.target_rate
    metadata["reviewSamplingBucket"] = review_sampling.bucket
    metadata["reviewSamplingStratum"] = review_sampling.stratum
    metadata["reviewSamplingPolicyVersion"] = review_sampling.policy_version
    metadata["reviewSamplingRecordedAt"] = review_sampling.recorded_at
    return run.model_copy(update={"metadata": metadata})
