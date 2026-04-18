from __future__ import annotations

import json
from datetime import UTC, datetime

from ds_agent.memory.semantic.infrastructure.adapters import UnityCatalogAdapter


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_unity_catalog_adapter_builds_table_trust_from_metadata_payload() -> None:
    requests: list[object] = []

    def _open_url(request, timeout: float):
        requests.append((request, timeout))
        return _FakeResponse(
            {
                "tables": [
                    {
                        "full_name": "main.analytics.orders",
                        "owner": "finance_steward",
                        "updated_at": "2026-04-16T03:00:00Z",
                        "comment": "Curated orders table",
                        "tags": {"trust_grade": "gold", "domain": "finance"},
                        "lineage_complete": True,
                        "refresh": {"cadence": "hourly", "max_staleness_minutes": 60},
                        "columns": [
                            {
                                "name": "order_id",
                                "type": "string",
                                "lineage_upstream": ["raw.orders.order_id"],
                            }
                        ],
                    }
                ]
            }
        )

    adapter = UnityCatalogAdapter(
        "https://unity.example/catalog",
        auth_token="secret-token",
        open_url=_open_url,
    )

    tables = adapter.fetch_tables(None)

    assert len(tables) == 1
    table = tables[0]
    assert table.fqtn == "main.analytics.orders"
    assert table.grade.value == "gold"
    assert table.owner == "finance_steward"
    assert table.refresh.cadence == "hourly"
    assert table.refresh.max_staleness_minutes == 60
    assert table.refresh.last_refreshed_at == datetime(2026, 4, 16, 3, 0, tzinfo=UTC)
    assert table.columns[0].column == "order_id"
    assert table.columns[0].lineage_upstream == ["raw.orders.order_id"]
    request, timeout = requests[0]
    assert request.full_url == "https://unity.example/catalog"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert timeout == 15.0


def test_unity_catalog_adapter_filters_old_tables_and_infers_silver_from_lineage() -> None:
    adapter = UnityCatalogAdapter(
        "https://unity.example/catalog",
        open_url=lambda request, timeout: _FakeResponse(
            {
                "tables": [
                    {
                        "catalog": "main",
                        "schema": "analytics",
                        "name": "stale_orders",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "columns": [],
                    },
                    {
                        "catalog": "main",
                        "schema": "analytics",
                        "name": "recent_orders",
                        "updated_at": "2026-04-16T04:30:00Z",
                        "columns": [
                            {
                                "name": "customer_id",
                                "type": "string",
                                "lineage_upstream": ["raw.orders.customer_id"],
                            }
                        ],
                    },
                ]
            }
        ),
    )

    tables = adapter.fetch_tables(datetime(2026, 4, 1, tzinfo=UTC))

    assert [table.fqtn for table in tables] == ["main.analytics.recent_orders"]
    assert tables[0].grade.value == "silver"
