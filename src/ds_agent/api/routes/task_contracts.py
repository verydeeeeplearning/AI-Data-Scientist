"""Task contract and delivery HTTP endpoints for desktop and operator surfaces."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

from ds_agent.application.dtos.task_contract import (
    BuildDeliveryPackDTO,
    DispatchDeliveryDTO,
    ListDeliveryLogDTO,
    RenderDeliveryArtifactDTO,
    TaskContractUpdateDTO,
    TaskContractViewDTO,
    VerifyAssumptionDTO,
)
from ds_agent.domain.entities.delivery_pack import DeliveryChannel
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.errors.task_contract_errors import (
    TaskContractError,
    TaskContractNotFoundError,
    VersionConflictError,
)
from ds_agent.domain.services.task_contract_state_machine import TaskContractValidator
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.infrastructure.task_contract_container import (
    TaskContractContainer,
    build_task_contract_container,
)
from ds_agent.infrastructure.verifier_container import (
    VerifierContainer,
    build_verifier_container,
)
from ds_agent.runtime.provider_factory import create_provider_router

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/task-contracts", tags=["task-contracts"])

_DEFAULT_INCLUDE = [
    "goal_brief",
    "metric_specs",
    "dataset_manifest",
    "assumption_log",
    "review_verdicts",
    "delivery_pack",
]


class TaskContractUpdateRequest(BaseModel):
    expected_version: int = Field(alias="expectedVersion", ge=1)
    patch: dict[str, Any] = Field(default_factory=dict)
    transition_to: TaskContractStatus | None = Field(default=None, alias="transitionTo")
    reason: str | None = None


class TaskContractCloseRequest(BaseModel):
    expected_version: int = Field(alias="expectedVersion", ge=1)
    closing_note: str = Field(alias="closingNote", min_length=1)


class AssumptionVerifyRequest(BaseModel):
    expected_version: int = Field(alias="expectedVersion", ge=1)
    verification_note: str | None = Field(default=None, alias="verificationNote")


class DeliveryPackBuildRequest(BaseModel):
    audiences: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list, alias="followUpActions")
    source_analysis_id: str | None = Field(default=None, alias="sourceAnalysisId")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    signed_by: str | None = Field(default=None, alias="signedBy")
    signature: str | None = None
    global_context: dict[str, str] = Field(default_factory=dict, alias="globalContext")
    tenant: str = Field(default="default", min_length=1)


class DeliveryArtifactRenderRequest(BaseModel):
    analysis: dict[str, Any] | str
    output_dir: str = Field(alias="outputDir", min_length=1)
    audience_profile: AudiencePersona | None = Field(default=None, alias="audienceProfile")
    provider_backed: bool = Field(default=False, alias="providerBacked")
    model: str | None = None

    @model_validator(mode="after")
    def _validate_provider_opt_in(self) -> DeliveryArtifactRenderRequest:
        if self.model and not self.provider_backed:
            raise ValueError("model requires providerBacked=true")
        return self


class DeliveryDispatchRequest(BaseModel):
    artifact_ids: list[str] = Field(default_factory=list, alias="artifactIds")
    channels: list[DeliveryChannel] = Field(default_factory=list)
    dry_run: bool = Field(default=False, alias="dryRun")
    approve_manual_review: bool = Field(default=False, alias="approveManualReview")


@router.get("")
async def list_task_contracts(
    request: Request,
    session_id: Annotated[str | None, Query(alias="sessionId")] = None,
    status: Annotated[list[TaskContractStatus] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, list[dict[str, Any]]]:
    """List task contracts, optionally filtered by session or status."""

    container = _container_for_request(request)
    items = container.list_contracts.execute(
        session_id,
        status_filter=list(status) if status else None,
        limit=limit,
    )
    return {"contracts": [item.model_dump(mode="json") for item in items]}


@router.get("/active")
async def get_active_task_contract(
    request: Request,
    session_id: Annotated[str, Query(alias="sessionId")],
    include: Annotated[list[str] | None, Query()] = None,
) -> dict[str, dict[str, Any] | None]:
    """Return the most recent non-terminal contract for a session."""

    bundle = _container_for_request(request).store.get_active_bundle(session_id)
    if bundle is None:
        return {"contract": None}
    return {"contract": _view_from_bundle(bundle, include).model_dump(mode="json")}


@router.get("/{task_id}")
async def get_task_contract(
    task_id: str,
    request: Request,
    include: Annotated[list[str] | None, Query()] = None,
) -> dict[str, dict[str, Any]]:
    """Return one detailed task contract view."""

    container = _container_for_request(request)
    try:
        view = container.get.execute(task_id, include=include or _DEFAULT_INCLUDE)
    except TaskContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"contract": view.model_dump(mode="json")}


@router.post("/{task_id}/update")
async def update_task_contract(
    task_id: str,
    request: Request,
    body: TaskContractUpdateRequest,
) -> dict[str, Any]:
    """Patch or transition a task contract."""

    container = _container_for_request(request)
    try:
        result = container.update.execute(
            TaskContractUpdateDTO.model_validate(
                {
                    "task_id": task_id,
                    "expected_version": body.expected_version,
                    "patch": body.patch,
                    "transition_to": body.transition_to,
                    "reason": body.reason,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.post("/{task_id}/close")
async def close_task_contract(
    task_id: str,
    request: Request,
    body: TaskContractCloseRequest,
) -> dict[str, Any]:
    """Close a reviewed task contract."""

    container = _container_for_request(request)
    try:
        result = container.close.execute(
            task_id,
            expected_version=body.expected_version,
            closing_note=body.closing_note,
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.post("/{task_id}/assumptions/{entry_id}/verify")
async def verify_assumption(
    task_id: str,
    entry_id: str,
    request: Request,
    body: AssumptionVerifyRequest,
) -> dict[str, Any]:
    """Mark one assumption entry as verified."""

    container = _container_for_request(request)
    try:
        result = container.verify_assumption.execute(
            VerifyAssumptionDTO.model_validate(
                {
                    "task_id": task_id,
                    "entry_id": entry_id,
                    "expected_version": body.expected_version,
                    "verification_note": body.verification_note,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.post("/{task_id}/delivery-pack/build")
async def build_delivery_pack(
    task_id: str,
    request: Request,
    body: DeliveryPackBuildRequest,
) -> dict[str, Any]:
    """Derive a delivery pack from required deliverables."""

    container = _container_for_request(request)
    try:
        result = container.build_delivery_pack.execute(
            BuildDeliveryPackDTO.model_validate(
                {
                    "task_id": task_id,
                    "audiences": body.audiences,
                    "follow_up_actions": body.follow_up_actions,
                    "source_analysis_id": body.source_analysis_id,
                    "confidence": body.confidence,
                    "signed_by": body.signed_by,
                    "signature": body.signature,
                    "global_context": body.global_context,
                    "tenant": body.tenant,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.post("/{task_id}/delivery-artifacts/{artifact_id}/render")
async def render_delivery_artifact(
    task_id: str,
    artifact_id: str,
    request: Request,
    body: DeliveryArtifactRenderRequest,
) -> dict[str, Any]:
    """Render one stored delivery artifact to a concrete file."""

    container, renderer_model = _render_container_for_request(
        request,
        provider_backed=body.provider_backed,
        model=body.model,
    )
    dto = RenderDeliveryArtifactDTO.model_validate(
        {
            "task_id": task_id,
            "artifact_id": artifact_id,
            "analysis": body.analysis,
            "output_dir": body.output_dir,
            "audience_profile": body.audience_profile,
        }
    )
    try:
        result = await asyncio.to_thread(
            container.render_delivery_artifact.execute,
            dto,
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    if renderer_model is not None:
        result["renderer_mode"] = "provider-backed"
        result["renderer_model"] = renderer_model
    return {"result": result}


@router.post("/{task_id}/delivery/dispatch")
async def dispatch_delivery(
    task_id: str,
    request: Request,
    body: DeliveryDispatchRequest,
) -> dict[str, Any]:
    """Dispatch rendered delivery artifacts through configured channels."""

    container = _container_for_request(request)
    try:
        result = container.dispatch_delivery.execute(
            DispatchDeliveryDTO.model_validate(
                {
                    "task_id": task_id,
                    "artifact_ids": body.artifact_ids,
                    "channels": body.channels,
                    "dry_run": body.dry_run,
                    "approve_manual_review": body.approve_manual_review,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.get("/{task_id}/delivery/log")
async def list_delivery_log(
    task_id: str,
    request: Request,
    pack_id: Annotated[str | None, Query(alias="packId")] = None,
    artifact_ids: Annotated[list[str] | None, Query(alias="artifactId")] = None,
    channels: Annotated[list[str] | None, Query(alias="channel")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict[str, Any]:
    """Return persisted delivery dispatch-log records for one task contract."""

    container = _container_for_request(request)
    try:
        result = container.list_delivery_log.execute(
            ListDeliveryLogDTO.model_validate(
                {
                    "task_id": task_id,
                    "pack_id": pack_id,
                    "artifact_ids": artifact_ids or [],
                    "channels": channels or [],
                    "limit": limit,
                }
            )
        )
    except Exception as exc:  # pragma: no cover - exercised through helper
        _raise_contract_http_error(exc)
    return {"result": result}


@router.get("/{task_id}/shadow-comparisons")
async def list_shadow_comparisons(
    task_id: str,
    request: Request,
    verdict_id: Annotated[str | None, Query(alias="verdictId")] = None,
    mismatches_only: Annotated[bool, Query(alias="mismatchesOnly")] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Return persisted verifier shadow comparison records for one task contract."""

    repo = _verifier_container_for_request(request).shadow_repo
    records = repo.list_for_task(task_id)
    if verdict_id:
        records = [record for record in records if record.verdict_id == verdict_id]
    if mismatches_only:
        records = [record for record in records if record.mismatch_count > 0]
    return {"comparisons": [record.model_dump(mode="json") for record in records[:limit]]}


@router.get("/{task_id}/shadow-comparisons/{comparison_id}")
async def get_shadow_comparison(
    task_id: str,
    comparison_id: str,
    request: Request,
) -> dict[str, Any]:
    """Return one persisted verifier shadow comparison record."""

    record = _verifier_container_for_request(request).shadow_repo.get(comparison_id)
    if record is None or record.task_id != task_id:
        raise HTTPException(
            status_code=404,
            detail=f"shadow comparison not found: {comparison_id}",
        )
    return {"comparison": record.model_dump(mode="json")}


def _container_for_request(request: Request) -> TaskContractContainer:
    state: AppState = request.app.state.app_state
    return build_task_contract_container(str(state.config.agent.workspace_dir))


def _render_container_for_request(
    request: Request,
    *,
    provider_backed: bool,
    model: str | None,
) -> tuple[TaskContractContainer, str | None]:
    state: AppState = request.app.state.app_state
    workspace_dir = str(state.config.agent.workspace_dir)
    if not provider_backed:
        return build_task_contract_container(workspace_dir), None
    resolved_model = model or state.config.provider.default_model
    provider = create_provider_router(
        resolved_model,
        state.config,
        token_store=state.token_store,
    )
    return (
        build_task_contract_container(workspace_dir, llm_provider=provider),
        resolved_model,
    )


def _verifier_container_for_request(request: Request) -> VerifierContainer:
    state: AppState = request.app.state.app_state
    return build_verifier_container(str(state.config.agent.workspace_dir))


def _view_from_bundle(
    bundle: TaskContractBundle,
    include: list[str] | None,
) -> TaskContractViewDTO:
    return TaskContractViewDTO.from_bundle(
        bundle,
        include=set(include or _DEFAULT_INCLUDE),
        dod_summary=TaskContractValidator.build_dod_summary(bundle),
    )


def _raise_contract_http_error(exc: Exception) -> None:
    if isinstance(exc, TaskContractNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, VersionConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (TaskContractError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc
