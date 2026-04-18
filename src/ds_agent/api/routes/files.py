"""File and plot serving endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
async def list_files(request: Request, project_id: str | None = None) -> dict:
    """List files in the workspace or a specific project."""
    state: AppState = request.app.state.app_state
    return {"files": state.list_files(project_id)}


# SEC-06: Only serve safe file types through the plot endpoint
_ALLOWED_PLOT_TYPES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".html", ".pdf"})


@router.get("/plots/{file_path:path}")
async def get_plot(request: Request, file_path: str) -> FileResponse:
    """Serve a plot image file from the workspace."""
    state: AppState = request.app.state.app_state
    base = Path(state.config.agent.workspace_dir).expanduser().resolve()
    full_path = (base / file_path).resolve()

    # SEC: ensure the resolved path is under the workspace (is_relative_to, not startswith)
    if not full_path.is_relative_to(base):
        raise HTTPException(status_code=403, detail="Access denied")

    # SEC-06: Only serve allowed file types
    if full_path.suffix.lower() not in _ALLOWED_PLOT_TYPES:
        raise HTTPException(status_code=403, detail="File type not allowed")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)
