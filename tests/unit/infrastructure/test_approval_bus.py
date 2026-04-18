"""Tests for the approval bus runtime and ask_user tool."""

from __future__ import annotations

import asyncio
import json

import pytest

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.tool_runtime_context import (
    ToolRuntimeContext,
    reset_tool_runtime_context,
    set_tool_runtime_context,
)


class TestJsonApprovalStore:
    def test_create_and_resolve(self, tmp_path):
        store = JsonApprovalStore(base_dir=tmp_path)
        created = store.create(
            session_id="session-1",
            run_id="run-1",
            surface="ws",
            question="Approve training?",
            kind="semantic_proposal",
            metadata={"proposalId": "SP-1"},
            options=["yes", "no"],
        )

        store.resolve(
            created.approval_id,
            status=ApprovalStatus.APPROVED,
            response="yes",
            source="ws",
            actor="user",
        )

        loaded = JsonApprovalStore(base_dir=tmp_path).get(created.approval_id)
        assert loaded is not None
        assert loaded.kind == "semantic_proposal"
        assert loaded.metadata["proposalId"] == "SP-1"
        assert loaded.status == ApprovalStatus.APPROVED
        assert loaded.response == "yes"
        assert loaded.source == "ws"

    @pytest.mark.asyncio
    async def test_wait_for_resolution_reads_persisted_update(self, tmp_path):
        store = JsonApprovalStore(base_dir=tmp_path)
        created = store.create(
            session_id="session-1",
            run_id="run-1",
            surface="ws",
            question="Approve training?",
        )

        async def _resolve() -> None:
            await asyncio.sleep(0.05)
            store.resolve(created.approval_id, status=ApprovalStatus.REJECTED, response="stop")

        task = asyncio.create_task(_resolve())
        resolved = await store.wait_for_resolution(created.approval_id)
        await task

        assert resolved.status == ApprovalStatus.REJECTED
        assert resolved.response == "stop"


class TestAskUser:
    @pytest.mark.asyncio
    async def test_waits_for_approval_and_returns_response(self, tmp_path):
        from ds_agent.tools.user_interaction import ask_user

        store = JsonApprovalStore(base_dir=tmp_path)
        events: list[tuple[str, dict]] = []
        token = set_tool_runtime_context(
            ToolRuntimeContext(
                session_id="session-1",
                run_id="run-1",
                surface="ws",
                emit_event=lambda event, payload: events.append((event, payload)),
                approval_store=store,
            )
        )
        try:

            async def _resolve() -> None:
                await asyncio.sleep(0.05)
                pending = store.latest_pending_for_session("session-1")
                assert pending is not None
                store.resolve(
                    pending.approval_id,
                    status=ApprovalStatus.APPROVED,
                    response="use target",
                    source="ws",
                )

            task = asyncio.create_task(_resolve())
            result = await ask_user("Which target should I use?", options=["target_a", "target_b"])
            await task
        finally:
            reset_tool_runtime_context(token)

        parsed = json.loads(result)
        assert parsed["type"] == "user_input"
        assert parsed["status"] == "approved"
        assert parsed["response"] == "use target"
        assert [event for event, _ in events] == ["approval.requested", "approval.resolved"]

    @pytest.mark.asyncio
    async def test_rejection_returns_error_payload(self, tmp_path):
        from ds_agent.tools.user_interaction import ask_user

        store = JsonApprovalStore(base_dir=tmp_path)
        token = set_tool_runtime_context(
            ToolRuntimeContext(
                session_id="session-2",
                run_id="run-2",
                surface="ws",
                emit_event=None,
                approval_store=store,
            )
        )
        try:

            async def _resolve() -> None:
                await asyncio.sleep(0.05)
                pending = store.latest_pending_for_session("session-2")
                assert pending is not None
                store.resolve(
                    pending.approval_id,
                    status=ApprovalStatus.REJECTED,
                    response="do not proceed",
                    source="telegram",
                )

            task = asyncio.create_task(_resolve())
            result = await ask_user("Should I deploy?")
            await task
        finally:
            reset_tool_runtime_context(token)

        parsed = json.loads(result)
        assert parsed["status"] == "rejected"
        assert parsed["error"] == "Approval rejected by user"
