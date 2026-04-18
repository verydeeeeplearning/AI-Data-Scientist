"""Background task manager tests."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.session_checkpoint import SessionCheckpoint
from ds_agent.runtime.background_task_manager import BackgroundTaskManager


async def _wait_for(predicate, timeout_seconds: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise TimeoutError("condition not satisfied before timeout")


class TestBackgroundTaskManager:
    @pytest.mark.asyncio
    async def test_background_task_start_and_status_tracking(self):
        started = asyncio.Event()
        finish = asyncio.Event()

        async def runner(session_id: str, prompt: str, **kwargs: object) -> str:
            started.set()
            await finish.wait()
            return "Training completed."

        manager = BackgroundTaskManager(runner=runner)
        task = manager.start(session_id="session-1", prompt="Train overnight")

        await started.wait()
        await _wait_for(lambda: manager.get(task.task_id).status == "running")
        finish.set()
        record = await manager.wait(task.task_id, timeout_seconds=1.0)

        assert record.status == "completed"
        assert record.result_preview == "Training completed."

    @pytest.mark.asyncio
    async def test_resume_uses_checkpoint_payload(self):
        captured: dict[str, object] = {}

        class StubCheckpointStore:
            def load(self, session_id: str) -> SessionCheckpoint | None:
                return SessionCheckpoint(
                    session_id=session_id,
                    step=4,
                    messages=[ChatMessage(role=Role.USER, content="checkpoint context")],
                )

        async def runner(session_id: str, prompt: str, **kwargs: object) -> str:
            captured["checkpoint"] = kwargs.get("resume_from_checkpoint")
            return "Resumed successfully."

        manager = BackgroundTaskManager(
            runner=runner,
            checkpoint_store=StubCheckpointStore(),
        )
        task = manager.start(
            session_id="session-2",
            prompt="Resume overnight training",
            resume_from_checkpoint=True,
        )
        record = await manager.wait(task.task_id, timeout_seconds=1.0)

        checkpoint = captured["checkpoint"]
        assert isinstance(checkpoint, SessionCheckpoint)
        assert checkpoint.step == 4
        assert record.resumed_from_checkpoint is True
        assert record.checkpoint_step == 4

    @pytest.mark.asyncio
    async def test_completion_notification_is_emitted(self):
        emit_event = MagicMock()

        async def runner(session_id: str, prompt: str, **kwargs: object) -> str:
            return "Background job done."

        manager = BackgroundTaskManager(runner=runner, emit_event=emit_event)
        task = manager.start(session_id="session-3", prompt="Generate report")
        await manager.wait(task.task_id, timeout_seconds=1.0)

        emitted = [call.args[0] for call in emit_event.call_args_list]
        assert "task.started" in emitted
        assert "task.completed" in emitted
