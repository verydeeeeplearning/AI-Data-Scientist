"""Backend-authoritative evidence workspace export endpoints."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ds_agent.api.dependencies import require_resource_access
from ds_agent.application.use_cases.list_run_artifacts_usecase import (
    ListRunArtifactsUseCase,
)
from ds_agent.infrastructure.artifact.exporters import supported_formats

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/export", tags=["export"])


async def _extract_path_from_body(request: Request) -> str:
    """Read ``path`` from the JSON body for export-file authorisation."""
    try:
        payload = await request.json()
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("path") or ""
    return value if isinstance(value, str) else ""


class WorkspaceFileExportRequest(BaseModel):
    """Request payload for file-level export reuse."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    format: str = Field(min_length=1)
    audience: Literal["ds", "exec", "ml"] | None = None


@router.get("/runs/{run_id}/artifacts")
async def list_run_artifacts(
    run_id: str,
    request: Request,
    include_archived_cards: bool = Query(default=False, alias="includeArchivedCards"),
    card_limit: int = Query(default=100, alias="cardLimit", ge=1, le=500),
) -> dict[str, Any]:
    """Return a compact run/workspace evidence snapshot."""

    state: AppState = request.app.state.app_state
    use_case = ListRunArtifactsUseCase(
        run_lookup=state,
        card_store=state.result_card_store,
        workspace_files=state,
        export_formats_for_suffix=supported_formats,
    )
    try:
        return await asyncio.to_thread(
            use_case.execute,
            run_id=run_id,
            include_archived_cards=include_archived_cards,
            card_limit=card_limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/file",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="workspace_file",
                action="export",
                resource_id_extractor=_extract_path_from_body,
            )
        )
    ],
)
async def export_workspace_file(
    body: WorkspaceFileExportRequest,
    request: Request,
) -> dict[str, Any]:
    """Reuse the existing workspace export machinery for one file."""

    state: AppState = request.app.state.app_state
    try:
        exported = await asyncio.to_thread(
            state.export_file,
            body.path,
            body.format,
            body.audience,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"export": exported}
