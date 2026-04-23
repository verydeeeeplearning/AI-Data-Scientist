"""HTTP routes for approval grants.

Wave 2 W2-F phase 2: settings UI and audit tooling list and revoke
session/workspace grants without going through the WebSocket approval bus.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ds_agent.api.dependencies import require_resource_access
from ds_agent.application.use_cases.approval_grant_usecases import (
    ListApprovalGrantsUseCase,
    RevokeApprovalGrantUseCase,
)

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/approval/grants", tags=["approval-grants"])


@router.get("")
async def list_approval_grants(
    request: Request,
    session_id: str | None = Query(default=None, alias="sessionId"),
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    include_inactive: bool = Query(default=False, alias="includeInactive"),
) -> dict[str, Any]:
    """Return matching approval grants. Active by default."""

    state: AppState = request.app.state.app_state
    store = _resolve_store(state)
    use_case = ListApprovalGrantsUseCase(store)
    grants = await asyncio.to_thread(
        use_case.execute,
        session_id=session_id,
        workspace_id=workspace_id,
        include_inactive=include_inactive,
    )
    return {"grants": grants}


@router.post(
    "/{grant_id}/revoke",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="approval_grant",
                action="mutate",
                resource_id_extractor=lambda req: req.path_params.get("grant_id", ""),
            )
        )
    ],
)
async def revoke_approval_grant(
    grant_id: str,
    request: Request,
) -> dict[str, Any]:
    """Mark a grant as revoked. Idempotent for already-revoked grants."""

    state: AppState = request.app.state.app_state
    store = _resolve_store(state)
    use_case = RevokeApprovalGrantUseCase(store)
    try:
        grant = await asyncio.to_thread(use_case.execute, grant_id, actor="settings-ui")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"grant": grant}


def _resolve_store(state: AppState) -> Any:
    store = getattr(state, "approval_grant_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="approval grant store unavailable")
    return store
