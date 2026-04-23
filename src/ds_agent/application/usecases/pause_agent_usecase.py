"""Pause the active agent run for a Mission Header session."""

from __future__ import annotations

from typing import Protocol

from ds_agent.application.dtos.pause_agent_dto import (
    PauseAgentRequestDTO,
    PauseAgentResultDTO,
)


class AbortRunPort(Protocol):
    async def __call__(self, *, session_id: str) -> object | None: ...


class PauseAgentUseCase:
    """Translate a Mission Header pause action into a backend abort call."""

    def __init__(self, abort_run: AbortRunPort) -> None:
        self._abort_run = abort_run

    async def execute(self, request: PauseAgentRequestDTO) -> PauseAgentResultDTO:
        run = await self._abort_run(session_id=request.session_id)
        if run is None:
            return PauseAgentResultDTO(paused=False, previousStatus="idle")
        return PauseAgentResultDTO(paused=True, previousStatus="running")
