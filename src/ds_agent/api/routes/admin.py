"""Admin HTTP routes for team and enterprise controls."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(tags=["admin"])

_DEFAULT_ORG_ACTOR = "local-user"


@router.get("/admin/audit-log/export")
async def export_audit_log(
    request: Request,
    start_date: Annotated[date, Query(alias="startDate")],
    end_date: Annotated[date, Query(alias="endDate")],
    format: Annotated[Literal["csv", "jsonl"], Query()] = "csv",
    actor_id: Annotated[str, Query(alias="actorId")] = _DEFAULT_ORG_ACTOR,
) -> Response:
    """Return an organization audit-log export as CSV or JSONL."""
    state: AppState = request.app.state.app_state

    try:
        payload = state.export_audit_log(
            actor_id=actor_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            format=format,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 403 if "admin" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return Response(
        content=str(payload["content"]),
        media_type=str(payload["contentType"]),
        headers={
            "Content-Disposition": f'attachment; filename="{payload["filename"]}"',
        },
    )
