"""HTTP route for owner access-log inspection."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Query, Request

from ds_agent.application.use_cases.list_access_log_usecase import (
    ListAccessLogInput,
    ListAccessLogUseCase,
)
from ds_agent.domain.access.access_log_entry import AccessLogEntry

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/access-log", tags=["access-log"])

_DEFAULT_OWNER_OPERATOR_ID = "local-user"


@router.get("")
async def list_access_log(
    request: Request,
    operator_id: Annotated[str, Query(alias="operatorId")] = _DEFAULT_OWNER_OPERATOR_ID,
    resource_type: Annotated[str | None, Query(alias="resourceType")] = None,
    since: Annotated[float | None, Query()] = None,
    until: Annotated[float | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, list[dict[str, Any]]]:
    """Return a newest-first slice of the redacted access log."""

    state: AppState = request.app.state.app_state
    use_case = ListAccessLogUseCase(state.access_log_store)
    entries = await asyncio.to_thread(
        use_case.execute,
        ListAccessLogInput(
            operator_id=operator_id,
            resource_type=resource_type,
            since=since,
            until=until,
            limit=limit,
        ),
    )
    return {"entries": [_serialize_entry(entry) for entry in entries]}


def _serialize_entry(entry: AccessLogEntry) -> dict[str, Any]:
    payload = asdict(entry)
    return {
        "entryId": payload["entry_id"],
        "resourceType": payload["resource_type"],
        "resourceId": payload["resource_id"],
        "action": payload["action"],
        "actorRef": payload["actor_ref"],
        "allowed": payload["allowed"],
        "role": payload["role"],
        "reason": payload["reason"],
        "metadata": payload["metadata"],
        "createdAt": payload["created_at"],
    }
