"""Integration tests for sql_query with QueryCostGuardHook."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.core import DSAgent
from ds_agent.agent.hooks import HookRegistry
from ds_agent.agent.query_cost_guard_hook import QueryCostGuardHook
from ds_agent.agent.semantic_hooks import SemanticTrustHook
from ds_agent.application.services.warehouse_service import (
    clear_warehouse_adapters,
    set_warehouse_adapter,
)
from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.messages import LLMResponse, ToolCall, Usage
from ds_agent.runtime.approval_store import JsonApprovalStore


class FakeWarehouseAdapter:
    def __init__(self, *, rows: list[dict], estimated_cost_usd: float) -> None:
        self._rows = rows
        self._estimated_cost_usd = estimated_cost_usd

    def execute_query(self, spec):
        return list(self._rows)

    def get_schemas(self):
        return []

    def get_tables(self, schema: str):
        return []

    def get_columns(self, schema: str, table: str):
        return []

    def estimate_cost(self, spec):
        from ds_agent.domain.value_objects.connector import CostEstimate

        return CostEstimate(
            estimated_rows=len(self._rows),
            estimated_cost_usd=self._estimated_cost_usd,
        )

    def validate_query(self, sql: str):
        from ds_agent.domain.value_objects.connector import SqlValidationResult

        return SqlValidationResult(is_safe=True)


@pytest.fixture(autouse=True)
def _reset_warehouse_registry() -> None:
    clear_warehouse_adapters()
    yield
    clear_warehouse_adapters()


class TestSqlQueryIntegration:
    @pytest.mark.asyncio
    async def test_sql_query_runs_through_cost_guard_and_tool(
        self,
        make_mock_provider,
    ) -> None:
        import ds_agent.tools.sql_tools  # noqa: F401
        from ds_agent.tools.registry import ToolRegistry

        set_warehouse_adapter(
            "default",
            FakeWarehouseAdapter(
                rows=[{"count": 321}],
                estimated_cost_usd=1.25,
            ),
        )

        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="sql_query",
                            arguments={"sql": "SELECT count(*) AS count FROM users"},
                        )
                    ],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="done",
                    usage=Usage(input_tokens=100, output_tokens=30),
                ),
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        hook = QueryCostGuardHook(max_cost_per_query_usd=10.0, max_cost_per_session_usd=20.0)
        hook_registry = HookRegistry()
        hook_registry.register(hook)

        agent = DSAgent(
            provider=provider,
            tool_registry=ToolRegistry,
            hook_registry=hook_registry,
            callbacks=callbacks,
        )

        result = await agent.run("How many users are there?")

        assert result == "done"
        tool_name, tool_args = callbacks.on_tool_start.call_args.args
        assert tool_name == "sql_query"
        assert tool_args["estimated_cost_usd"] == pytest.approx(1.25)

        _, tool_result, is_error = callbacks.on_tool_end.call_args.args
        assert is_error is False
        payload = json.loads(tool_result)
        assert payload["row_count"] == 1
        assert payload["data"] == [[321]]
        assert hook._session_cost_usd == pytest.approx(1.25)

    @pytest.mark.asyncio
    async def test_semantic_trust_hook_blocks_bronze_table_query(
        self,
        make_mock_provider,
        monkeypatch,
        tmp_path,
    ) -> None:
        import ds_agent.tools.sql_tools  # noqa: F401
        from ds_agent.tools.registry import ToolRegistry

        provider = make_mock_provider(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="sql_query",
                            arguments={"sql": "SELECT * FROM prod.growth.subscription"},
                        )
                    ],
                    usage=Usage(input_tokens=100, output_tokens=50),
                ),
                LLMResponse(
                    content="done",
                    usage=Usage(input_tokens=100, output_tokens=30),
                ),
            ]
        )

        callbacks = MagicMock()
        callbacks.on_step = AsyncMock()
        callbacks.on_status = AsyncMock()
        callbacks.on_tool_start = AsyncMock()
        callbacks.on_tool_end = AsyncMock()
        callbacks.on_budget_warning = AsyncMock()
        callbacks.on_stream_delta = AsyncMock()
        callbacks.emit_event = MagicMock()

        @dataclass
        class _Table:
            fqtn: str

        @dataclass
        class _TrustResult:
            action: str = "confirm"
            warnings: list[str] = field(
                default_factory=lambda: ["manual confirmation required for bronze/untrusted table"]
            )
            missing_tables: list[str] = field(default_factory=list)
            tables: list[object] = field(
                default_factory=lambda: [_Table("prod.growth.subscription")]
            )

        class _TrustUseCase:
            def execute(self, tables: list[str]):
                return _TrustResult()

        class _Container:
            check_table_trust = _TrustUseCase()

        monkeypatch.setattr(
            "ds_agent.agent.semantic_hooks.get_semantic_memory_container",
            lambda: _Container(),
        )

        hook_registry = HookRegistry()
        hook_registry.register(SemanticTrustHook())
        approval_store = JsonApprovalStore(base_dir=tmp_path)

        agent = DSAgent(
            provider=provider,
            tool_registry=ToolRegistry,
            hook_registry=hook_registry,
            callbacks=callbacks,
            approval_store=approval_store,
            session_id="session-1",
        )

        result = await agent.run("Show churn from bronze table")

        assert result == "done"
        _, tool_result, is_error = callbacks.on_tool_end.call_args.args
        assert is_error is True
        assert "[DENIED]" in tool_result
        pending = approval_store.latest_pending_for_session("session-1")
        assert pending is not None
        assert pending.status == ApprovalStatus.PENDING
