"""Tests for sandbox.violation event emission from `run_ds_sandbox`.

Phase A of P0-01 Phase 3 UI: the sandbox runtime collects violations into
`SandboxResult.violations`, but until now they were only embedded in the
JSON error string returned to the LLM. The Electron renderer cannot show
them to the user.

This module pins the new behavior: when violations are present and the
runtime context exposes `emit_event`, the runner emits one
`sandbox.violation` event per violation, with a stable payload shape
mirroring `event_schemas.SandboxViolationEvent`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.sandbox import SandboxViolation, ViolationKind
from ds_agent.runtime.tool_runtime_context import (
    ToolRuntimeContext,
    reset_tool_runtime_context,
    set_tool_runtime_context,
)
from ds_agent.tools._ds_sandbox_runner import run_ds_sandbox
from ds_agent.tools.sandbox import SandboxResult


@pytest.fixture
def captured_events():
    """Provide a list that captures every `emit_event(name, payload)` call."""
    return []


@pytest.fixture
def runtime_context(captured_events):
    """Install a ToolRuntimeContext whose emit_event records into a list."""

    def _emit(name: str, payload: dict) -> None:
        captured_events.append((name, payload))

    ctx = ToolRuntimeContext(
        session_id="session-abc",
        run_id="run-xyz",
        surface="electron",
        emit_event=_emit,
    )
    token = set_tool_runtime_context(ctx)
    try:
        yield ctx
    finally:
        reset_tool_runtime_context(token)


def _mock_sandbox(result: SandboxResult) -> MagicMock:
    sb = MagicMock()
    sb.execute = AsyncMock(return_value=result)
    return sb


@pytest.mark.asyncio
async def test_blocked_filesystem_violation_emits_event(captured_events, runtime_context):
    violation = SandboxViolation(
        kind=ViolationKind.FILESYSTEM,
        detail="open('/etc/passwd', 'w') blocked by workspace policy",
        blocked=True,
    )
    sandbox = _mock_sandbox(
        SandboxResult(
            success=False,
            stdout="",
            stderr="SANDBOX_VIOLATION ...",
            return_code=1,
            violations=(violation,),
        )
    )

    with patch(
        "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=sandbox
    ):
        await run_ds_sandbox(code="print(1)", tool_name="run_eda", timeout=10)

    violation_events = [evt for evt in captured_events if evt[0] == "sandbox.violation"]
    assert len(violation_events) == 1
    _name, payload = violation_events[0]
    assert payload["kind"] == "filesystem"
    assert payload["detail"] == violation.detail
    assert payload["blocked"] is True
    assert payload["sessionId"] == "session-abc"
    assert payload["runId"] == "run-xyz"
    assert payload["tool"] == "run_eda"
    assert isinstance(payload["timestamp"], float)


@pytest.mark.asyncio
async def test_resource_violation_emits_event(captured_events, runtime_context):
    violation = SandboxViolation(
        kind=ViolationKind.RESOURCE,
        detail="memory limit (256 MB) exceeded",
        blocked=True,
    )
    sandbox = _mock_sandbox(
        SandboxResult(
            success=False,
            stdout="",
            stderr="MemoryError",
            return_code=137,
            violations=(violation,),
        )
    )

    with patch(
        "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=sandbox
    ):
        await run_ds_sandbox(code="x=[0]*10**9", tool_name="run_eda", timeout=10)

    violation_events = [evt for evt in captured_events if evt[0] == "sandbox.violation"]
    assert len(violation_events) == 1
    assert violation_events[0][1]["kind"] == "resource"


@pytest.mark.asyncio
async def test_multiple_violations_emit_one_event_each(captured_events, runtime_context):
    violations = (
        SandboxViolation(kind=ViolationKind.SUBPROCESS, detail="os.system blocked"),
        SandboxViolation(kind=ViolationKind.FILESYSTEM, detail="write outside workspace"),
    )
    sandbox = _mock_sandbox(
        SandboxResult(
            success=False,
            stdout="",
            stderr="...",
            return_code=1,
            violations=violations,
        )
    )

    with patch(
        "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=sandbox
    ):
        await run_ds_sandbox(code="...", tool_name="train_model", timeout=10)

    violation_events = [evt for evt in captured_events if evt[0] == "sandbox.violation"]
    assert len(violation_events) == 2
    kinds = {evt[1]["kind"] for evt in violation_events}
    assert kinds == {"subprocess", "filesystem"}


@pytest.mark.asyncio
async def test_successful_execution_emits_no_violation_event(captured_events, runtime_context):
    sandbox = _mock_sandbox(
        SandboxResult(success=True, stdout="ok", stderr="", return_code=0, violations=())
    )

    with patch(
        "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=sandbox
    ):
        await run_ds_sandbox(code="print(1)", tool_name="run_eda", timeout=10)

    violation_events = [evt for evt in captured_events if evt[0] == "sandbox.violation"]
    assert violation_events == []


@pytest.mark.asyncio
async def test_no_emit_event_in_context_does_not_raise():
    """When the runtime context has no emit_event, runner must not crash."""
    ctx = ToolRuntimeContext(
        session_id="s",
        run_id="r",
        surface="cli",
        emit_event=None,
    )
    token = set_tool_runtime_context(ctx)
    try:
        sandbox = _mock_sandbox(
            SandboxResult(
                success=False,
                stdout="",
                stderr="x",
                return_code=1,
                violations=(
                    SandboxViolation(kind=ViolationKind.FILESYSTEM, detail="x", blocked=True),
                ),
            )
        )
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=sandbox
        ):
            result = await run_ds_sandbox(code="...", tool_name="run_eda", timeout=10)
        assert "error" in result.lower()
    finally:
        reset_tool_runtime_context(token)
