from __future__ import annotations

from unittest.mock import patch

from ds_agent.domain.entities.runtime_state import RuntimeStatus
from ds_agent.runtime.run_registry import RunRegistry
from ds_agent.runtime.session_registry import RuntimeSessionRegistry


def test_runtime_session_registry_persists_last_run(tmp_path) -> None:
    registry = RuntimeSessionRegistry(workspace_dir=str(tmp_path))

    with patch("ds_agent.runtime.session_registry.time.time", return_value=100.0):
        registry.ensure("session-1", "ws")
    with patch("ds_agent.runtime.session_registry.time.time", return_value=125.0):
        registry.bind_run("session-1", "run-1", "daemon")

    reloaded = RuntimeSessionRegistry(workspace_dir=str(tmp_path))
    session = reloaded.get("session-1")

    assert session is not None
    assert session.surface == "daemon"
    assert session.created_at == 100.0
    assert session.last_active == 125.0
    assert session.last_run_id == "run-1"


def test_run_registry_persists_lifecycle_across_reloads(tmp_path) -> None:
    sessions = RuntimeSessionRegistry(workspace_dir=str(tmp_path))
    registry = RunRegistry(sessions, workspace_dir=str(tmp_path))

    with patch("ds_agent.runtime.run_registry.time.time", return_value=200.0):
        run = registry.create("session-2", "ws", "Analyze cohort retention.")
    registry.attach_task(run.run_id, "task-2")
    with patch("ds_agent.runtime.run_registry.time.time", return_value=245.0):
        registry.mark_succeeded(run.run_id, result="Done.", cost_usd=0.55)

    reloaded_sessions = RuntimeSessionRegistry(workspace_dir=str(tmp_path))
    reloaded = RunRegistry(reloaded_sessions, workspace_dir=str(tmp_path))
    restored = reloaded.get(run.run_id)

    assert restored is not None
    assert restored.session_id == "session-2"
    assert restored.status == RuntimeStatus.SUCCEEDED
    assert restored.started_at == 200.0
    assert restored.finished_at == 245.0
    assert restored.task_id == "task-2"
    assert restored.cost_usd == 0.55
    assert reloaded.latest_for_session("session-2") is not None
