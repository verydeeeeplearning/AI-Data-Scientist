"""Tests for sql_query tool and SQL result summarization."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from ds_agent.application.services.warehouse_service import (
    clear_warehouse_adapters,
    set_warehouse_adapter,
)
from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import CostEstimate, QuerySpec, SqlValidationResult
from ds_agent.tools.path_utils import set_active_workspace


class FakeWarehouseAdapter:
    """Deterministic warehouse adapter for tool tests."""

    def __init__(
        self,
        *,
        rows: list[dict],
        estimated_cost_usd: float = 0.0,
    ) -> None:
        self._rows = rows
        self._estimated_cost_usd = estimated_cost_usd
        self.executed_specs: list[QuerySpec] = []

    def execute_query(self, spec: QuerySpec) -> list[dict]:
        self.executed_specs.append(spec)
        return list(self._rows)

    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="analytics")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        return [TableInfo(name="users", schema=schema)]

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        return [ColumnInfo(name="id", data_type="integer", nullable=False)]

    def estimate_cost(self, spec: QuerySpec) -> CostEstimate:
        return CostEstimate(
            estimated_rows=len(self._rows),
            estimated_cost_usd=self._estimated_cost_usd,
        )

    def validate_query(self, sql: str) -> SqlValidationResult:
        return SqlValidationResult(is_safe=True)


@pytest.fixture(autouse=True)
def _reset_warehouse_registry() -> None:
    clear_warehouse_adapters()
    set_active_workspace(None)
    yield
    clear_warehouse_adapters()
    set_active_workspace(None)


class TestSqlQueryTool:
    @pytest.mark.asyncio
    async def test_sql_query_returns_rows_and_cost(self) -> None:
        from ds_agent.tools.sql_tools import sql_query

        set_warehouse_adapter(
            "default",
            FakeWarehouseAdapter(
                rows=[{"count": 12345}],
                estimated_cost_usd=2.5,
            ),
        )

        result = await sql_query("SELECT count(*) AS count FROM users")
        payload = json.loads(result)

        assert payload["columns"] == ["count"]
        assert payload["data"] == [[12345]]
        assert payload["row_count"] == 1
        assert payload["cost_usd"] == 2.5
        assert payload["truncated"] is False
        assert payload["summary_stats"]["count"]["mean"] == 12345.0

    @pytest.mark.asyncio
    async def test_large_result_is_summarized_and_saved_to_workspace(self) -> None:
        from ds_agent.tools.sql_tools import sql_query

        rows = [
            {
                "user_id": idx,
                "score": float(idx),
                "segment": "vip" if idx % 2 == 0 else "standard",
            }
            for idx in range(10_000)
        ]
        workspace = Path.cwd() / ".codex_sql_tool_test" / uuid4().hex
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            set_active_workspace(workspace)
            set_warehouse_adapter(
                "default",
                FakeWarehouseAdapter(rows=rows, estimated_cost_usd=4.2),
            )

            result = await sql_query("SELECT user_id, score, segment FROM analytics.users")
            payload = json.loads(result)

            assert payload["row_count"] == 10_000
            assert len(payload["data"]) == 20
            assert payload["truncated"] is True
            assert payload["cost_usd"] == 4.2
            assert payload["summary_stats"]["user_id"]["min"] == 0
            assert payload["summary_stats"]["user_id"]["max"] == 9_999
            assert payload["summary_stats"]["score"]["mean"] == pytest.approx(4_999.5)
            assert payload["summary_stats"]["segment"]["top_values"][0]["value"] in {
                "vip",
                "standard",
            }

            saved_path = Path(payload["saved_result_path"])
            assert saved_path.exists()
            assert saved_path.is_relative_to(workspace)
            assert saved_path.suffix == ".csv"
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_sql_query_rejects_unsafe_sql(self) -> None:
        from ds_agent.tools.sql_tools import sql_query

        set_warehouse_adapter("default", FakeWarehouseAdapter(rows=[]))

        result = await sql_query("DROP TABLE users")
        payload = json.loads(result)

        assert "error" in payload
        assert "safety" in payload["error"].lower()
