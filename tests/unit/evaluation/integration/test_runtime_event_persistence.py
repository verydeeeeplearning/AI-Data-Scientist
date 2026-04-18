from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ds_agent.agent.callbacks import NullCallbacks


async def test_foreground_run_persists_started_and_completed_runtime_events(tmp_path) -> None:
    from ds_agent.api.ws_handler import AppState
    from ds_agent.config.schema import AgentConfig, DSAgentConfig

    class FakeAgent:
        def __init__(self) -> None:
            self._budget = MagicMock()
            self._budget.state = MagicMock()
            self._budget.state.total_cost_usd = 0.42
            self._budget.get_summary = MagicMock(
                return_value={
                    "input_tokens": 10,
                    "output_tokens": 12,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "reasoning_tokens": 0,
                    "cache_savings_usd": 0.0,
                }
            )

        def set_runtime_context(self, run_id=None, surface=None) -> None:
            return None

        async def run(self, message: str, **kwargs: object) -> str:
            return "Finished successfully."

    config = DSAgentConfig(agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")))
    state = AppState(config=config)
    fake_agent = FakeAgent()

    with patch.object(state._sessions, "get_or_create", new=AsyncMock(return_value=fake_agent)):
        run = await state.start_run(
            session_id="ws-session-1",
            message="Analyze this cohort.",
            callbacks=NullCallbacks(),
            surface="ws",
        )
        await state.wait_for_run(run.run_id, timeout_ms=1000)

    events = state.list_runtime_events(limit=10, session_id="ws-session-1", category="task")
    kinds = [event.kind for event in events]
    assert "task.started" in kinds
    assert "task.completed" in kinds
