"""Network runner sandbox tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ds_agent.tools.sandbox import SandboxResult


class _FakeApproval:
    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id


class _FakeApprovalStore:
    def __init__(self) -> None:
        self.created_questions: list[str] = []

    def create(
        self,
        *,
        session_id: str,
        run_id: str | None,
        surface: str,
        question: str,
        options: list[str] | None = None,
        default: str | None = None,
    ) -> _FakeApproval:
        self.created_questions.append(question)
        return _FakeApproval("approval-123")


class TestNetworkRunnerSandbox:
    @pytest.mark.asyncio
    async def test_denies_without_approval(self) -> None:
        from ds_agent.tools.network_sandbox import NetworkRunnerSandbox

        approval_store = _FakeApprovalStore()
        sandbox = NetworkRunnerSandbox(
            timeout=5,
            approval_store=approval_store,
            session_id="session-1",
            run_id="run-1",
            surface="ws",
        )

        result = await sandbox.execute("print('network')")

        assert result.success is False
        assert "approval" in result.stderr.lower()
        assert approval_store.created_questions
        assert sandbox.audit_log[-1]["status"] == "approval_required"

    @pytest.mark.asyncio
    async def test_allows_after_policy_approval_and_records_audit(self) -> None:
        from ds_agent.tools.network_sandbox import NetworkRunnerSandbox

        mock_result = SandboxResult(
            success=True,
            stdout="ok",
            stderr="",
            return_code=0,
        )

        with patch(
            "ds_agent.tools.network_sandbox.ProcessSandbox.execute",
            new=AsyncMock(return_value=mock_result),
        ) as mocked_execute:
            sandbox = NetworkRunnerSandbox(
                timeout=5,
                approved=True,
                session_id="session-1",
                run_id="run-1",
                surface="ws",
            )
            result = await sandbox.execute("print('network')")

        assert result.success is True
        mocked_execute.assert_awaited_once()
        assert sandbox.audit_log[-1]["status"] == "executed"
        assert sandbox.audit_log[-1]["session_id"] == "session-1"
