"""Web push HTTP routes (Wave 4 PLAN_06b infrastructure close)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ds_agent.api.dependencies.access import require_resource_access
from ds_agent.infrastructure.persistence.web_push_subscription_store import (
    WebPushSubscription,
)
from ds_agent.runtime.web_push_subject_store import WebPushSubjectError

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/web-push", tags=["web-push"])

# Sole-user fallback: matches ``_DEFAULT_ORG_ACTOR`` semantics in
# :mod:`ds_agent.api.ws_handler`.
_DEFAULT_OPERATOR_ID = "local-user"

_SUBJECT_WRITE_GUARD = require_resource_access(
    resource_type="config",
    action="mutate",
    resource_id_extractor=lambda _request: "workspace",
)


def _coerce_operator_id(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _DEFAULT_OPERATOR_ID


def _coerce_str(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    keys = payload.get("keys")
    if isinstance(keys, dict):
        for name in names:
            inner = keys.get(name)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def _resolve_subject_source(state: AppState) -> tuple[str | None, str | None]:
    subject = state.web_push_subject_store.load()
    if subject:
        return subject, "config"
    env_subject = os.environ.get("DS_AGENT_VAPID_SUBJECT", "").strip()
    if env_subject:
        return env_subject, "env"
    return None, None


@router.get("/public-key")
async def get_public_key(request: Request) -> dict[str, Any]:
    """Return the VAPID public key, or ``None`` when push is disabled."""

    state: AppState = request.app.state.app_state
    public_key = getattr(state, "vapid_public_key", None)
    return {"publicKey": public_key}


@router.get("/subject")
async def get_subject(request: Request) -> dict[str, Any]:
    """Return the configured VAPID subject and its source."""

    state: AppState = request.app.state.app_state
    subject, source = _resolve_subject_source(state)
    return {"subject": subject, "source": source}


@router.post("/subject", dependencies=[Depends(_SUBJECT_WRITE_GUARD)])
async def set_subject(request: Request) -> dict[str, Any]:
    """Persist a new VAPID subject."""

    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - JSON guard
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    subject = _coerce_str(payload, "subject")
    if not subject:
        raise HTTPException(status_code=400, detail="subject is required")

    state: AppState = request.app.state.app_state
    try:
        saved = state.web_push_subject_store.save(subject)
    except WebPushSubjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "subject": saved, "source": "config"}


@router.get("/metrics")
async def get_metrics(
    request: Request,
    operator_id: Annotated[str | None, Query(alias="operatorId")] = None,
    window_hours: Annotated[int, Query(alias="windowHours")] = 24,
) -> dict[str, Any]:
    """Return per-subscription health metrics for the requested window."""

    if window_hours < 1:
        raise HTTPException(status_code=400, detail="windowHours must be at least 1")

    state: AppState = request.app.state.app_state
    operator_id = _coerce_operator_id(operator_id)
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    summary = state.web_push_metrics_store.summary(operator_id, since)
    return {
        "operatorId": operator_id,
        "windowHours": window_hours,
        "since": since.isoformat(),
        "deliveredCount": summary.delivered_count,
        "failedCount": summary.failed_count,
        "prunedCount": summary.pruned_count,
        "uniqueEndpoints": summary.unique_endpoints,
    }


@router.post("/subscriptions")
async def register_subscription(request: Request) -> dict[str, Any]:
    """Register or refresh one browser PushManager subscription."""

    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - JSON guard
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    endpoint = _coerce_str(payload, "endpoint")
    p256dh = _coerce_str(payload, "p256dhKey", "p256dh_key", "p256dh")
    auth = _coerce_str(payload, "authKey", "auth_key", "auth")

    if not endpoint or not p256dh or not auth:
        raise HTTPException(
            status_code=400,
            detail="endpoint, p256dh, and auth are required",
        )

    operator_id = _coerce_operator_id(payload.get("operatorId") or payload.get("operator_id"))
    state: AppState = request.app.state.app_state
    subscription = WebPushSubscription(
        endpoint=endpoint,
        p256dh_key=p256dh,
        auth_key=auth,
        created_at=datetime.now(UTC),
    )
    store = state.web_push_subscription_store
    store.register(operator_id, subscription)
    return {"ok": True, "endpoint": endpoint, "operatorId": operator_id}


@router.post("/subscriptions/unregister")
async def unregister_subscription(request: Request) -> dict[str, Any]:
    """Drop one subscription by endpoint."""

    try:
        payload = await request.json()
    except Exception as exc:  # pragma: no cover - JSON guard
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    endpoint = _coerce_str(payload, "endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint is required")

    operator_id = _coerce_operator_id(payload.get("operatorId") or payload.get("operator_id"))
    state: AppState = request.app.state.app_state
    removed = state.web_push_subscription_store.unregister(operator_id, endpoint)
    return {"ok": True, "endpoint": endpoint, "removed": removed}


__all__ = ["router"]
