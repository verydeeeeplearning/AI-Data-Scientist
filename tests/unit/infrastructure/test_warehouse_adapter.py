"""Warehouse adapter base behavior tests."""

from __future__ import annotations

import pytest

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import (
    ConnectorConfig,
    ConnectorType,
    CostEstimate,
    QuerySpec,
)
from ds_agent.infrastructure.persistence.base import BaseWarehouseAdapter
from ds_agent.infrastructure.persistence.errors import ReadOnlyViolationError


class FakeAdapter(BaseWarehouseAdapter):
    def __init__(
        self,
        config: ConnectorConfig,
        *,
        rows: list[dict] | None = None,
        simulated_query_seconds: int = 0,
    ) -> None:
        super().__init__(config)
        self._rows = rows or [{"value": 1}]
        self._simulated_query_seconds = simulated_query_seconds
        self.last_timeout_seconds: int | None = None

    def _execute_query_impl(self, spec: QuerySpec, *, timeout_seconds: int) -> list[dict]:
        self.last_timeout_seconds = timeout_seconds
        if self._simulated_query_seconds > timeout_seconds:
            raise TimeoutError(
                "Query exceeded timeout "
                f"{timeout_seconds}s (needed {self._simulated_query_seconds}s)"
            )
        return list(self._rows)

    def _get_schemas_impl(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="analytics")]

    def _get_tables_impl(self, schema: str) -> list[TableInfo]:
        return [TableInfo(name="users", schema=schema)]

    def _get_columns_impl(self, schema: str, table: str) -> list[ColumnInfo]:
        return [ColumnInfo(name="user_id", data_type="integer", nullable=False)]

    def _estimate_cost_impl(self, spec: QuerySpec) -> CostEstimate:
        return CostEstimate(estimated_rows=len(self._rows), estimated_cost_usd=0.05)


class TestWarehouseAdapterBase:
    def test_execute_query_returns_rows(self) -> None:
        adapter = FakeAdapter(
            ConnectorConfig(type=ConnectorType.POSTGRES, host="localhost", database="analytics")
        )

        rows = adapter.execute_query(QuerySpec(sql="SELECT 1 AS value"))

        assert rows == [{"value": 1}]

    def test_read_only_blocks_ddl_dml(self) -> None:
        adapter = FakeAdapter(
            ConnectorConfig(type=ConnectorType.POSTGRES, host="localhost", database="analytics")
        )

        with pytest.raises(ReadOnlyViolationError, match="SQL safety violation"):
            adapter.execute_query(QuerySpec(sql="DROP TABLE users"))

    def test_timeout_is_capped_by_config(self) -> None:
        adapter = FakeAdapter(
            ConnectorConfig(
                type=ConnectorType.POSTGRES,
                host="localhost",
                database="analytics",
                timeout_seconds=30,
            ),
            simulated_query_seconds=31,
        )

        with pytest.raises(TimeoutError, match="30s"):
            adapter.execute_query(QuerySpec(sql="SELECT * FROM users", timeout_override=60))

        assert adapter.last_timeout_seconds == 30

    def test_large_results_are_truncated_to_configured_max_rows(self) -> None:
        adapter = FakeAdapter(
            ConnectorConfig(
                type=ConnectorType.POSTGRES,
                host="localhost",
                database="analytics",
                max_rows=10,
            ),
            rows=[{"idx": idx} for idx in range(100)],
        )

        rows = adapter.execute_query(QuerySpec(sql="SELECT * FROM users"))

        assert len(rows) == 10
        assert rows[0] == {"idx": 0}
        assert rows[-1] == {"idx": 9}
