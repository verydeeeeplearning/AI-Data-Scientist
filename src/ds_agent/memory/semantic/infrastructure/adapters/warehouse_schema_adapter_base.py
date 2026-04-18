"""Common base for schema-driven external semantic adapters."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

from ds_agent.domain.interfaces.warehouse import ColumnInfo, WarehouseAdapter
from ds_agent.domain.value_objects.connector import ConnectorConfig
from ds_agent.memory.semantic.application.ports import ExternalSemanticSource
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import (
    ColumnTrust,
    PiiClass,
    RefreshCadence,
    RefreshSLA,
    TableTrust,
    TrustGrade,
)
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

_PII_COLUMN_TOKENS = ("email", "phone", "mobile", "ssn", "tax", "passport")


class WarehouseSchemaAdapterBase(ExternalSemanticSource):
    """Common sync behavior for warehouse schema-to-trust adapters."""

    def __init__(
        self,
        connector: ConnectorConfig,
        warehouse_adapter: WarehouseAdapter,
        *,
        owner: str | None = None,
        include_schemas: Sequence[str] | None = None,
        exclude_schemas: Sequence[str] | None = None,
        refresh_cadence: RefreshCadence = "daily",
        max_staleness_minutes: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connector = connector
        self._warehouse_adapter = warehouse_adapter
        self._owner = owner or connector.label or connector.name
        self._include_schemas = self._normalize_schema_names(include_schemas)
        self._exclude_schemas = self._normalize_schema_names(exclude_schemas)
        self._refresh_cadence = refresh_cadence
        self._max_staleness_minutes = (
            max_staleness_minutes
            if max_staleness_minutes is not None
            else default_max_staleness_minutes(refresh_cadence)
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self.name = connector.name

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return []

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return []

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        audited_at = self._clock().date()
        return [
            self._build_table_trust(schema_name, table.name, audited_at=audited_at)
            for schema_name in self._iter_schemas()
            for table in self._warehouse_adapter.get_tables(schema_name)
        ]

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return []

    def _iter_schemas(self) -> list[str]:
        configured_schemas = self._configured_schemas()
        if configured_schemas:
            return configured_schemas

        return [
            schema.name
            for schema in self._warehouse_adapter.get_schemas()
            if not self._is_system_schema(schema.name) and schema.name not in self._exclude_schemas
        ]

    def _configured_schemas(self) -> list[str]:
        if self._include_schemas:
            return [name for name in self._include_schemas if name not in self._exclude_schemas]

        schema_option = self._connector.get_option("include_schemas")
        normalized_option_schemas = self._normalize_schema_names(schema_option)
        if normalized_option_schemas:
            return [
                name for name in normalized_option_schemas if name not in self._exclude_schemas
            ]

        schema_list_option = self._normalize_schema_names(self._connector.get_option("schemas"))
        if schema_list_option:
            return [name for name in schema_list_option if name not in self._exclude_schemas]

        if self._connector.schema and not self._is_system_schema(self._connector.schema):
            return [self._connector.schema]
        return []

    def _build_table_trust(
        self,
        schema_name: str,
        table_name: str,
        *,
        audited_at: date,
    ) -> TableTrust:
        fqtn = f"{self._connector.database}.{schema_name}.{table_name}"
        columns = self._warehouse_adapter.get_columns(schema_name, table_name)
        return TableTrust(
            fqtn=fqtn,
            grade=TrustGrade.SILVER,
            owner=self._owner,
            description=f"Auto-synced schema metadata for {fqtn}.",
            refresh=RefreshSLA(
                cadence=self._refresh_cadence,
                max_staleness_minutes=self._max_staleness_minutes,
            ),
            columns=[build_column_trust(column) for column in columns],
            approved_joins=[],
            grade_rationale=self._grade_rationale(),
            last_audited=audited_at,
        )

    def _grade_rationale(self) -> str:
        return (
            "Auto-seeded from warehouse metadata. Defaulted to silver until human audit "
            "promotes or downgrades the table."
        )

    def _is_system_schema(self, schema_name: str) -> bool:
        del schema_name
        return False

    @staticmethod
    def _normalize_schema_names(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Sequence):
            normalized: list[str] = []
            for item in value:
                name = str(item).strip()
                if name:
                    normalized.append(name)
            return normalized
        return []


def build_column_trust(column: ColumnInfo) -> ColumnTrust:
    pii_class: PiiClass = "low" if is_pii_column(column) else "none"
    return ColumnTrust(
        column=column.name,
        pii_class=pii_class,
        lineage_upstream=[],
        nullable_ratio=None,
        data_type=column.data_type,
    )


def is_pii_column(column: ColumnInfo) -> bool:
    if column.is_pii:
        return True
    inferred = column.inferred_meaning.casefold()
    if inferred == "pii":
        return True
    name = column.name.casefold()
    return any(token in name for token in _PII_COLUMN_TOKENS)


def default_max_staleness_minutes(cadence: str) -> int:
    defaults = {
        "realtime": 60,
        "hourly": 180,
        "daily": 1_440,
        "weekly": 10_080,
        "adhoc": 43_200,
    }
    return defaults.get(cadence, 1_440)
