"""HTTP endpoints for integration health and connector status."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/health")
async def integration_health(request: Request) -> dict[str, Any]:
    """Run health checks across all registered integration connectors."""
    app_state: AppState = request.app.state.app_state
    hub = _get_hub(app_state)
    if hub is None:
        return {"connectors": [], "error": "Integration hub not available."}
    results = hub.health_check_all()
    return {
        "connectors": [r.model_dump(mode="json") for r in results],
        "all_healthy": all(r.healthy for r in results),
    }


def _get_hub(app_state: AppState) -> Any:
    """Resolve the IntegrationHub from AppState, or None."""
    try:
        container = getattr(app_state, "_work_object_container", None)
        if container is None:
            from ds_agent.infrastructure.work_object_container import build_work_object_container

            workspace = getattr(app_state, "workspace_dir", None) or "."
            container = build_work_object_container(workspace)
        return getattr(container, "hub", None)
    except Exception:
        return None
