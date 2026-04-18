from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ds_agent.memory.semantic.infrastructure.adapters import DbtMetricFlowAdapter


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_dbt_metricflow_adapter_builds_metrics_from_graphql_payload() -> None:
    requests: list[object] = []

    def _open_url(request, timeout: float):
        requests.append((request, timeout))
        return _FakeResponse(
            {
                "data": {
                    "metrics": [
                        {
                            "name": "monthly_active_users",
                            "label": "Monthly Active Users",
                            "description": "MAU from dbt semantic layer",
                            "type": "count",
                            "filter": "is_active = true",
                            "aggregation": "COUNT(DISTINCT user_id)",
                            "semanticModel": "prod.product.user_activity",
                            "updatedAt": "2026-04-16T00:00:00Z",
                            "dimensions": ["country", "plan_tier"],
                            "metadata": {
                                "owner": "product_analytics",
                                "unit": "count",
                                "direction": "higher_is_better",
                                "synonyms": ["MAU"],
                            },
                            "relatedMetrics": ["weekly_active_users"],
                        }
                    ]
                }
            }
        )

    adapter = DbtMetricFlowAdapter(
        "https://dbt.example.com/graphql",
        auth_token="secret-token",
        open_url=_open_url,
    )

    metrics = adapter.fetch_metrics(None)

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.metric_id == "monthly_active_users"
    assert metric.owner == "product_analytics"
    assert metric.unit == "count"
    assert metric.direction == "higher_is_better"
    assert metric.calculation.numerator.source == "prod.product.user_activity"
    assert metric.calculation.numerator.aggregation == "COUNT(DISTINCT user_id)"
    assert "MAU" in metric.synonyms
    assert "Available dimensions: country, plan_tier" in metric.caveats
    request, timeout = requests[0]
    assert request.full_url == "https://dbt.example.com/graphql"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert timeout == 15.0


def test_dbt_metricflow_adapter_filters_metrics_older_than_since() -> None:
    adapter = DbtMetricFlowAdapter(
        "https://dbt.example.com/graphql",
        open_url=lambda request, timeout: _FakeResponse(
            {
                "data": {
                    "metrics": [
                        {
                            "name": "daily_signups",
                            "description": "Daily signups",
                            "type": "count",
                            "aggregation": "COUNT(*)",
                            "semanticModel": "prod.growth.signup",
                            "updatedAt": "2026-03-01T00:00:00Z",
                        }
                    ]
                }
            }
        ),
    )

    metrics = adapter.fetch_metrics(datetime(2026, 4, 1, tzinfo=UTC))

    assert metrics == []


def test_dbt_metricflow_adapter_raises_for_graphql_errors() -> None:
    adapter = DbtMetricFlowAdapter(
        "https://dbt.example.com/graphql",
        open_url=lambda request, timeout: _FakeResponse(
            {
                "errors": [{"message": "unauthorized"}],
                "data": {},
            }
        ),
    )

    with pytest.raises(ValueError, match="returned errors"):
        adapter.fetch_metrics(None)
