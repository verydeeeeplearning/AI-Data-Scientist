"""HTTP endpoints for backend-authoritative result-card reads and mutations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ds_agent.api.dependencies import (
    require_resource_access,
    require_session_mutation,
)
from ds_agent.application.use_cases.list_cards_by_session_usecase import (
    ListCardsBySessionUseCase,
)
from ds_agent.application.use_cases.pin_card_usecase import PinCardUseCase
from ds_agent.application.use_cases.render_card_for_audience_usecase import (
    CardAudience,
    RenderCardForAudienceUseCase,
)
from ds_agent.infrastructure.persistence.card_store import SqliteCardStore
from ds_agent.infrastructure.rendering.audience_renderer import AudienceRenderer

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState
    from ds_agent.domain.result_card import ResultCard

router = APIRouter(prefix="/api/cards", tags=["cards"])


async def _extract_card_id_from_body(request: Request) -> str:
    """Read ``cardId``/``card_id`` from the parsed JSON body."""
    try:
        payload = await request.json()
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("cardId") or payload.get("card_id") or ""
    return value if isinstance(value, str) else ""


class CardPinRequest(BaseModel):
    """Mutation payload for one card pinned state."""

    model_config = ConfigDict(extra="forbid")

    pinned: bool = Field(default=True)


class RenderForAudienceRequest(BaseModel):
    """Payload for backend-authored audience rendering."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    card_id: str = Field(alias="cardId", min_length=1)
    audience: CardAudience


class AudienceSwitchTelemetryRequest(BaseModel):
    """Payload for the audience-switch telemetry beacon."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_audience: CardAudience | None = Field(default=None, alias="fromAudience")
    to_audience: CardAudience = Field(alias="toAudience")
    session_id: str | None = Field(default=None, alias="sessionId")


@router.get("/session/{session_id}")
async def list_cards_by_session(
    session_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    include_archived: bool = Query(default=False, alias="includeArchived"),
) -> dict[str, Any]:
    """Return persisted cards for one session."""

    use_case = ListCardsBySessionUseCase(store=_card_store(request))
    cards = use_case.execute(
        session_id=session_id,
        limit=limit,
        include_archived=include_archived,
    )
    return {"cards": [_serialize_card(card) for card in cards]}


@router.post(
    "/render-for-audience",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="card",
                action="mutate",
                resource_id_extractor=_extract_card_id_from_body,
            )
        )
    ],
)
async def render_for_audience(
    payload: RenderForAudienceRequest,
    request: Request,
) -> dict[str, Any]:
    """Render one persisted card for an audience lens."""

    use_case = RenderCardForAudienceUseCase(
        store=_card_store(request),
        renderer=AudienceRenderer(),
    )
    rendered = await asyncio.to_thread(
        use_case.execute,
        card_id=payload.card_id,
        audience=payload.audience,
    )
    return {"renderedCard": rendered.model_dump(mode="json", by_alias=True)}


@router.post(
    "/audience-switch",
    dependencies=[Depends(require_session_mutation("workspace", "mutate"))],
)
async def record_audience_switch(
    payload: AudienceSwitchTelemetryRequest,
    request: Request,
) -> dict[str, Any]:
    """Record a workspace audience-switch beacon via the runtime-event log."""

    state: AppState = request.app.state.app_state
    if payload.from_audience == payload.to_audience:
        return {"recorded": False}

    event = state.record_runtime_event(
        category="workspace",
        kind="workspace.audience.switched",
        severity="info",
        message=(
            "Audience switched from "
            f"{payload.from_audience or 'unknown'} to {payload.to_audience}"
        ),
        session_id=payload.session_id,
        surface="renderer",
        source="electron",
        metadata={
            "fromAudience": payload.from_audience,
            "toAudience": payload.to_audience,
            "sessionId": payload.session_id,
        },
    )
    return {"recorded": True, "event": _serialize_runtime_event(event)}


@router.get("/{card_id}")
async def get_card(card_id: str, request: Request) -> dict[str, Any]:
    """Return one persisted card by identifier."""

    card = _card_store(request).get_card(card_id)
    if card is None:
        _raise_card_not_found(card_id)
    return {"card": _serialize_card(card)}


@router.post(
    "/{card_id}/pin",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="card",
                action="mutate",
                resource_id_extractor=lambda req: req.path_params.get("card_id", ""),
            )
        )
    ],
)
async def pin_card(
    card_id: str,
    payload: CardPinRequest,
    request: Request,
) -> dict[str, Any]:
    """Persist a card pinned state mutation."""

    try:
        card = PinCardUseCase(store=_card_store(request)).execute(
            card_id=card_id,
            pinned=payload.pinned,
        )
    except LookupError:
        _raise_card_not_found(card_id)
    return {"card": _serialize_card(card)}


def _card_store(request: Request) -> SqliteCardStore:
    state: AppState = request.app.state.app_state
    workspace_dir = str(state.config.agent.workspace_dir)
    return SqliteCardStore.for_workspace(workspace_dir)


def _serialize_card(card: ResultCard) -> dict[str, Any]:
    return card.model_dump(mode="json", by_alias=True)


def _serialize_runtime_event(event: object) -> dict[str, Any]:
    return {
        "eventId": getattr(event, "event_id", ""),
        "category": getattr(event, "category", "workspace"),
        "kind": getattr(event, "kind", ""),
        "severity": getattr(event, "severity", "info"),
        "message": getattr(event, "message", ""),
        "sessionId": getattr(event, "session_id", None),
        "runId": getattr(event, "run_id", None),
        "surface": getattr(event, "surface", "renderer"),
        "source": getattr(event, "source", "electron"),
        "metadata": dict(getattr(event, "metadata", {}) or {}),
        "createdAt": getattr(event, "created_at", 0.0),
    }


def _raise_card_not_found(card_id: str) -> NoReturn:
    raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")
