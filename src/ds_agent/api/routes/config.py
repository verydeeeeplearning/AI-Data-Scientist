"""GET/POST /api/config — configuration endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ds_agent.api.dependencies import require_resource_access

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api", tags=["config"])

# SEC-01: Whitelist of allowed config paths — single source of truth for both
# the HTTP endpoint and the WebSocket RPC handler (4.8 fix: no duplication).
ALLOWED_CONFIG_PATHS: frozenset[str] = frozenset(
    {
        "provider.quality_preset",
        "provider.default_model",
        "provider.max_budget_usd",
        "provider.budget_warning_threshold_pct",
        "agent.mode",
        "agent.max_iterations",
        "agent.workspace_dir",
        "agent.use_case_hint",
        "agent.use_case_context",
        "agent.context_window",
        "agent.auto_compress",
        "agent.language",  # P1-13: user-preferred response language
        "gateway.host",
        "gateway.port",
        "gateway.autonomous_runtime_enabled",
        "gateway.autonomous_cooldown_seconds",
        "gateway.autonomous_max_concurrent_runs",
        "gateway.autonomous_budget_per_run_usd",
        "gateway.automation_profile",
        "gateway.authority_overlay",
        "gateway.authority_overlay_started_at",
        "channels.telegram.enabled",
        "channels.telegram.allow_from",
        "observability.telemetry_enabled",
        "observability.error_reporting_enabled",
    }
)


class ConfigUpdateRequest(BaseModel):
    path: str
    value: Any


@router.get("/config")
async def get_config(request: Request) -> dict:
    """Return current configuration."""
    state: AppState = request.app.state.app_state
    return {"config": state.config_manager.get_dump()}


@router.post(
    "/config",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="config",
                action="mutate",
                resource_id_extractor=lambda req: "workspace",
            )
        )
    ],
)
async def set_config(request: Request, body: ConfigUpdateRequest) -> dict:
    """Update a config value by dotted path (e.g. 'provider.default_model').

    Delegates to ConfigManager which handles whitelist checks, validation,
    and automatic persistence for app-global settings (3.11).
    """
    state: AppState = request.app.state.app_state

    try:
        state.set_config(body.path, body.value)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    return {"ok": True}
