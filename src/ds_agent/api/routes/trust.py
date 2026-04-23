"""HTTP endpoint for trust metadata projection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from fastapi import APIRouter, HTTPException, Request

from ds_agent.application.use_cases.get_trust_metadata_usecase import (
    GetTrustMetadataUseCase,
)
from ds_agent.infrastructure.persistence.certification_store import SqliteCertificationStore
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.runtime_event_log import RuntimeEventLog

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/trust", tags=["trust"])


@router.get("/{result_id}")
async def get_trust_metadata(result_id: str, request: Request) -> dict[str, Any]:
    """Return the trust projection for one result identifier."""

    try:
        result = _trust_use_case(request).execute(result_id)
    except ValueError as exc:
        _raise_trust_http_error(exc)
    return {"trust": result.model_dump(mode="json", by_alias=True)}


def _trust_use_case(request: Request) -> GetTrustMetadataUseCase:
    state: AppState = request.app.state.app_state
    workspace_dir = str(state.config.agent.workspace_dir)
    return GetTrustMetadataUseCase(
        verdict_repo=SqliteVerdictRepository.for_workspace(workspace_dir),
        lineage_store=SqliteLineageStore(_lineage_db_path(workspace_dir)),
        certification_store=SqliteCertificationStore.for_workspace(workspace_dir),
        approval_store=JsonApprovalStore(workspace_dir),
        drift_store=SqliteDeployMonitorStateStore.for_workspace(workspace_dir),
        event_log=RuntimeEventLog(workspace_dir),
    )


def _lineage_db_path(workspace_dir: str) -> str:
    from pathlib import Path

    return str(Path(workspace_dir) / "data" / "memory" / "lineage.db")


def _raise_trust_http_error(exc: ValueError) -> NoReturn:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
