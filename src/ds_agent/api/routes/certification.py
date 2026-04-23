"""HTTP endpoints for mission certification status and submissions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ds_agent.api.dependencies import require_resource_access
from ds_agent.application.services.certification_usecases import (
    GetCertificationStatusUseCase,
    SubmitCertificationInput,
    SubmitCertificationResult,
    SubmitCertificationUseCase,
)
from ds_agent.domain.entities.certification import CertificationRecord, CertificationStats
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.skills.mission_pack_loader import MissionPackLoader

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState
    from ds_agent.application.services.certification_usecases import CertificationStatusResult

router = APIRouter(prefix="/api/certification", tags=["certification"])


class CertificationSubmitRequest(BaseModel):
    target_level: str = Field(alias="targetLevel", min_length=1)
    approved_by: tuple[str, ...] = Field(default_factory=tuple, alias="approvedBy")
    evidence_ref: str | None = Field(default=None, alias="evidenceRef")


@router.get("")
async def list_certification_statuses(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Return certification status snapshots for available mission packs."""

    loader = MissionPackLoader()
    store = SqliteCertificationStore.for_workspace(_workspace_dir(request))
    use_case = GetCertificationStatusUseCase(loader, store)

    missions: list[dict[str, Any]] = []
    for mission_name in loader.list_packs():
        try:
            missions.append(_serialize_status(use_case.execute(mission_name)))
        except ValueError:
            continue

    return {"missions": missions}


@router.get("/{mission_name}")
async def get_certification_status(
    mission_name: str,
    request: Request,
) -> dict[str, dict[str, Any]]:
    """Return one mission certification snapshot."""

    loader = MissionPackLoader()
    store = SqliteCertificationStore.for_workspace(_workspace_dir(request))
    try:
        result = GetCertificationStatusUseCase(loader, store).execute(mission_name)
    except ValueError as exc:
        _raise_certification_http_error(exc)
    return {"mission": _serialize_status(result)}


@router.post(
    "/{mission_name}/submit",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="certification",
                action="mutate",
                resource_id_extractor=lambda req: req.path_params.get("mission_name", ""),
            )
        )
    ],
)
async def submit_certification(
    mission_name: str,
    request: Request,
    body: CertificationSubmitRequest,
) -> dict[str, dict[str, Any]]:
    """Submit certification evidence and owner approvals for one mission."""

    loader = MissionPackLoader()
    store = SqliteCertificationStore.for_workspace(_workspace_dir(request))
    try:
        result = SubmitCertificationUseCase(loader, store).execute(
            SubmitCertificationInput(
                mission_name=mission_name,
                target_level=body.target_level,
                approved_by=body.approved_by,
                evidence_ref=body.evidence_ref,
            )
        )
    except ValueError as exc:
        _raise_certification_http_error(exc)
    return {"result": _serialize_submission(result)}


def _workspace_dir(request: Request) -> str:
    state: AppState = request.app.state.app_state
    return str(state.config.agent.workspace_dir)


def _serialize_status(result: CertificationStatusResult) -> dict[str, Any]:
    return {
        "mission_name": result.mission_name,
        "mission_version": result.mission_version,
        "current_level": _serialize_level(result.current_level),
        "effective_level": _serialize_level(result.effective_level),
        "next_target": _serialize_level(result.next_target),
        "required_approvers": result.required_approvers,
        "certified_for_next_target": result.certified_for_next_target,
        "gaps": list(result.gaps),
        "stats": _serialize_stats(result.stats),
        "latest_certification": _serialize_record(result.latest_certification),
    }


def _serialize_submission(result: SubmitCertificationResult) -> dict[str, Any]:
    return {
        "mission_name": result.mission_name,
        "mission_version": result.mission_version,
        "target_level": result.target_level.value,
        "status": result.status,
        "current_level": _serialize_level(result.current_level),
        "required_approvers": result.required_approvers,
        "approved_by": list(result.approved_by),
        "gaps": list(result.gaps),
        "stats": _serialize_stats(result.stats),
        "certification": _serialize_record(result.certification),
    }


def _serialize_stats(stats: CertificationStats) -> dict[str, Any]:
    return {
        "shadow_runs_passed": stats.shadow_runs_passed,
        "critical_violations": stats.critical_violations,
        "verifier_avg_score": stats.verifier_avg_score,
        "rollback_rehearsal_passed": stats.rollback_rehearsal_passed,
    }


def _serialize_record(record: CertificationRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "level": record.level.value,
        "transition_from": _serialize_level(record.transition_from),
        "approved_by": list(record.approved_by),
        "approved_at": record.approved_at.isoformat(),
        "evidence_ref": record.evidence_ref,
        "next_review": record.next_review.isoformat() if record.next_review is not None else None,
    }


def _serialize_level(value: object) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _raise_certification_http_error(exc: ValueError) -> NoReturn:
    message = str(exc)
    status_code = (
        404
        if "Mission pack not found" in message or "Invalid mission pack name" in message
        else 400
    )
    raise HTTPException(status_code=status_code, detail=message) from exc
