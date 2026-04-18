"""Warehouse adapter port interface (Domain layer).

Defines the abstract contract for database connectors.
Infrastructure layer provides concrete implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ds_agent.domain.value_objects.connector import CostEstimate, QuerySpec, SqlValidationResult


@dataclass
class ColumnInfo:
    """Column metadata."""

    name: str
    data_type: str
    nullable: bool = True
    description: str = ""
    inferred_meaning: str = ""  # identifier, timestamp, PII, metric, etc.
    is_pii: bool = False


@dataclass
class TableInfo:
    """Table metadata."""

    name: str
    schema: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count_estimate: int | None = None
    description: str = ""


@dataclass
class SchemaInfo:
    """Schema (namespace) metadata."""

    name: str
    tables: list[TableInfo] = field(default_factory=list)


@runtime_checkable
class WarehouseAdapter(Protocol):
    """Port interface for warehouse database adapters.

    All adapters must be read-only by default.
    """

    def execute_query(self, spec: QuerySpec) -> list[dict]:
        """Execute a read-only query and return rows as dicts."""
        ...

    def get_schemas(self) -> list[SchemaInfo]:
        """List available schemas."""
        ...

    def get_tables(self, schema: str) -> list[TableInfo]:
        """List tables in a schema."""
        ...

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        """List columns in a table."""
        ...

    def estimate_cost(self, spec: QuerySpec) -> CostEstimate:
        """Estimate query cost (bytes processed, USD)."""
        ...

    def validate_query(self, sql: str) -> SqlValidationResult:
        """Validate query safety (read-only check)."""
        ...
