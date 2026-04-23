"""Support bundle export endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ds_agent.api.dependencies import require_resource_access

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/support", tags=["support"])


class SupportBundleRequest(BaseModel):
    output_path: str = Field(alias="outputPath")


@router.post(
    "/bundle",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="support_bundle",
                action="export",
                resource_id_extractor=lambda req: "workspace",
            )
        )
    ],
)
async def export_support_bundle(request: Request, body: SupportBundleRequest) -> dict[str, str]:
    """Create a redacted support bundle ZIP at the requested output path."""
    state: AppState = request.app.state.app_state
    try:
        result = state.export_support_bundle(body.output_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"path": str(result)}
