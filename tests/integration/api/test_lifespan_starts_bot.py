from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from ds_agent.config.schema import AgentConfig, DSAgentConfig


class FakeAppState:
    instances: ClassVar[list[FakeAppState]] = []

    def __init__(self, *, enabled: bool, token: str, workspace_dir: str) -> None:
        self.config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=workspace_dir),
        )
        self.config.channels.telegram.enabled = enabled
        self.config.channels.telegram.bot_token = token
        self.supervisor: FakeBotSupervisor | None = None
        self.background_started = 0
        self.background_stopped = 0
        self.telegram_stopped = 0
        FakeAppState.instances.append(self)

    def set_telegram_supervisor(self, supervisor: Any) -> None:
        self.supervisor = supervisor

    async def start_background_runtime(self) -> None:
        self.background_started += 1

    async def stop_background_runtime(self) -> None:
        self.background_stopped += 1

    async def stop_telegram_gateway(self) -> None:
        self.telegram_stopped += 1
        if self.supervisor is not None:
            await self.supervisor.stop()


class FakeBotSupervisor:
    instances: ClassVar[list[FakeBotSupervisor]] = []

    def __init__(self, config: DSAgentConfig, *, app_state: FakeAppState) -> None:
        self.config = config
        self.app_state = app_state
        self.started = 0
        self.stopped = 0
        FakeBotSupervisor.instances.append(self)

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1


def test_lifespan_starts_telegram_supervisor_when_enabled(
    monkeypatch,
) -> None:
    from ds_agent.api import app as api_app
    from ds_agent.gateway import bot_supervisor as bot_supervisor_module

    workspace_dir = str(Path.cwd() / "tests" / "fixtures" / "telegram_lifespan_workspace")
    FakeAppState.instances.clear()
    FakeBotSupervisor.instances.clear()

    monkeypatch.setattr(
        api_app,
        "AppState",
        lambda: FakeAppState(
            enabled=True,
            token="123456:ABCDEFGHIJKLMNOPQRST",
            workspace_dir=workspace_dir,
        ),
    )
    monkeypatch.setattr(bot_supervisor_module, "BotSupervisor", FakeBotSupervisor)

    app = api_app.create_app(ws_token=None)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert FakeBotSupervisor.instances[0].started == 1
        assert FakeAppState.instances[0].background_started == 1

    assert FakeAppState.instances[0].telegram_stopped == 1
    assert FakeAppState.instances[0].background_stopped == 1
    assert FakeBotSupervisor.instances[0].stopped == 1


def test_lifespan_skips_telegram_autostart_without_enabled_token(
    monkeypatch,
) -> None:
    from ds_agent.api import app as api_app
    from ds_agent.gateway import bot_supervisor as bot_supervisor_module

    workspace_dir = str(Path.cwd() / "tests" / "fixtures" / "telegram_lifespan_workspace")
    FakeAppState.instances.clear()
    FakeBotSupervisor.instances.clear()

    monkeypatch.setattr(
        api_app,
        "AppState",
        lambda: FakeAppState(enabled=True, token="", workspace_dir=workspace_dir),
    )
    monkeypatch.setattr(bot_supervisor_module, "BotSupervisor", FakeBotSupervisor)

    app = api_app.create_app(ws_token=None)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert FakeBotSupervisor.instances[0].started == 0
        assert FakeAppState.instances[0].background_started == 1

    assert FakeBotSupervisor.instances[0].stopped == 1
