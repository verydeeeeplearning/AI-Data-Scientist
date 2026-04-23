from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from ds_agent.application.dtos.pause_agent_dto import PauseAgentRequestDTO
from ds_agent.application.usecases.pause_agent_usecase import PauseAgentUseCase


@dataclass
class _StubRun:
    run_id: str


class _StubAbort:
    def __init__(self, *, return_run: bool) -> None:
        self.calls: list[str] = []
        self._return_run = return_run

    async def __call__(self, *, session_id: str) -> object | None:
        self.calls.append(session_id)
        return _StubRun(run_id="run-1") if self._return_run else None


def test_pause_agent_returns_paused_when_active_run_exists() -> None:
    abort = _StubAbort(return_run=True)
    usecase = PauseAgentUseCase(abort)
    result = asyncio.run(
        usecase.execute(
            PauseAgentRequestDTO(sessionId="session-a", reason="budget_warning")
        )
    )
    assert result.paused is True
    assert result.previous_status == "running"
    assert abort.calls == ["session-a"]


def test_pause_agent_returns_idle_when_no_active_run() -> None:
    abort = _StubAbort(return_run=False)
    usecase = PauseAgentUseCase(abort)
    result = asyncio.run(
        usecase.execute(PauseAgentRequestDTO(sessionId="session-b", reason="manual"))
    )
    assert result.paused is False
    assert result.previous_status == "idle"
    assert abort.calls == ["session-b"]


def test_pause_agent_request_requires_session_id() -> None:
    with pytest.raises(Exception):
        PauseAgentRequestDTO(sessionId="", reason="manual")
