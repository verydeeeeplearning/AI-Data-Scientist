"""HTTP endpoints for workflow-integration work objects."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ds_agent.application.dtos.work_object import (
    AdvanceWorkObjectPhaseDTO,
    CloseWorkObjectDTO,
    CreateWorkObjectDTO,
    ListWorkObjectsDTO,
)
from ds_agent.domain.entities.external_reference import build_integration_idempotency_key
from ds_agent.domain.entities.work_object import RequestSource, WorkObjectPhase
from ds_agent.domain.errors.work_object_errors import (
    WorkObjectError,
    WorkObjectNotFoundError,
)
from ds_agent.infrastructure.work_object_container import (
    WorkObjectContainer,
    build_work_object_container,
)

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/work-objects", tags=["work-objects"])


class WorkObjectIntakeRequest(BaseModel):
    task_contract_id: str = Field(alias="taskContractId", min_length=1)
    title: str = Field(min_length=1)
    request_source: RequestSource = Field(alias="requestSource")
    requestor_id: str = Field(alias="requestorId", min_length=1)
    requestor_display: str = Field(alias="requestorDisplay", min_length=1)
    original_text: str = Field(alias="originalText", min_length=1)
    channel: str | None = None
    request_metadata: dict[str, Any] = Field(default_factory=dict, alias="requestMetadata")
    external_reference: dict[str, Any] | None = Field(default=None, alias="externalReference")
    delivery_pack_id: str | None = Field(default=None, alias="deliveryPackId")
    owner_agent: str = Field(default="ds-agent", alias="ownerAgent")
    tags: list[str] = Field(default_factory=list)
    parent_work_object_id: str | None = Field(default=None, alias="parentWorkObjectId")


class WorkObjectAdvanceRequest(BaseModel):
    to_phase: WorkObjectPhase = Field(alias="toPhase")
    run_id: str | None = Field(default=None, alias="runId")


class WorkObjectCloseRequest(BaseModel):
    reason: str = Field(min_length=1)


@router.get("")
async def list_work_objects(
    request: Request,
    session_id: Annotated[str | None, Query(alias="sessionId")] = None,
    task_contract_id: Annotated[str | None, Query(alias="taskContractId")] = None,
    phase: Annotated[list[WorkObjectPhase] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> dict[str, list[dict[str, Any]]]:
    """List work objects filtered by session, task contract, or phase."""

    items = _container_for_request(request).list_work_objects.execute(
        ListWorkObjectsDTO(
            session_id=session_id,
            task_contract_id=task_contract_id,
            phase_filter=list(phase) if phase else [],
            limit=limit,
        )
    )
    return {"work_objects": [item.model_dump(mode="json") for item in items]}


@router.post("/intake")
async def intake_work_object(
    request: Request,
    body: WorkObjectIntakeRequest,
) -> dict[str, Any]:
    """Create a work object from a structured inbound request."""

    external_reference = _normalize_external_reference(
        task_contract_id=body.task_contract_id,
        request_source=body.request_source,
        external_reference=body.external_reference,
    )
    try:
        view = _container_for_request(request).create.execute(
            CreateWorkObjectDTO.model_validate(
                {
                    "task_contract_id": body.task_contract_id,
                    "title": body.title,
                    "request_source": body.request_source,
                    "requestor_id": body.requestor_id,
                    "requestor_display": body.requestor_display,
                    "original_text": body.original_text,
                    "channel": body.channel,
                    "request_metadata": body.request_metadata,
                    "external_reference": external_reference,
                    "delivery_pack_id": body.delivery_pack_id,
                    "owner_agent": body.owner_agent,
                    "tags": body.tags,
                    "parent_work_object_id": body.parent_work_object_id,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_work_object_http_error(exc)
    return {"result": view.model_dump(mode="json")}


@router.get("/{work_object_id}")
async def get_work_object(
    work_object_id: str,
    request: Request,
    timeline_limit: Annotated[int, Query(alias="timelineLimit", ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """Return one detailed work object plus its persisted integration timeline."""

    try:
        view = _container_for_request(request).get.execute(
            work_object_id,
            timeline_limit=timeline_limit,
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_work_object_http_error(exc)
    return view.model_dump(mode="json")


@router.get("/{work_object_id}/timeline")
async def get_work_object_timeline(
    work_object_id: str,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    """Return the persisted integration timeline for one work object."""

    try:
        events = _container_for_request(request).timeline.execute(work_object_id, limit=limit)
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_work_object_http_error(exc)
    return {"events": [event.model_dump(mode="json") for event in events]}


@router.post("/{work_object_id}/phase")
async def advance_work_object_phase(
    work_object_id: str,
    request: Request,
    body: WorkObjectAdvanceRequest,
) -> dict[str, Any]:
    """Advance the work-object lifecycle phase."""

    try:
        result = _container_for_request(request).advance_phase.execute(
            AdvanceWorkObjectPhaseDTO.model_validate(
                {
                    "work_object_id": work_object_id,
                    "to_phase": body.to_phase,
                    "run_id": body.run_id,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_work_object_http_error(exc)
    return {"result": result}


@router.post("/{work_object_id}/close")
async def close_work_object(
    work_object_id: str,
    request: Request,
    body: WorkObjectCloseRequest,
) -> dict[str, Any]:
    """Close a work object once follow-up is complete."""

    try:
        result = _container_for_request(request).close.execute(
            CloseWorkObjectDTO.model_validate(
                {"work_object_id": work_object_id, "reason": body.reason}
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_work_object_http_error(exc)
    return {"result": result}


def _container_for_request(request: Request) -> WorkObjectContainer:
    state: AppState = request.app.state.app_state
    return build_work_object_container(str(state.config.agent.workspace_dir))


def _normalize_external_reference(
    *,
    task_contract_id: str,
    request_source: RequestSource,
    external_reference: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if external_reference is None:
        return None
    normalized = dict(external_reference)
    normalized.setdefault("metadata", {})
    normalized.setdefault("created_at", datetime.now(UTC).isoformat())
    normalized.setdefault(
        "idempotency_key",
        build_integration_idempotency_key(
            work_object_id=f"task-{task_contract_id}",
            system=str(normalized.get("system") or request_source.value),
            action="intake_request",
            discriminator=str(
                normalized.get("resource_id")
                or normalized.get("resource_type")
                or "request"
            ),
        ),
    )
    return normalized


def _raise_work_object_http_error(exc: Exception) -> None:
    if isinstance(exc, WorkObjectNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (WorkObjectError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc
