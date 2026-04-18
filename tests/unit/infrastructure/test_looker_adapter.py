from __future__ import annotations

import json
from datetime import UTC, datetime

from ds_agent.memory.semantic.infrastructure.adapters import LookerAdapter


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_looker_adapter_builds_metrics_glossary_and_verified_queries() -> None:
    requests: list[object] = []
    payload = {
        "views": [
            {
                "name": "user_activity",
                "sql_table_name": "prod.product.user_activity",
                "updated_at": "2026-04-16T01:00:00Z",
                "fields": [
                    {
                        "name": "monthly_active_users",
                        "type": "measure",
                        "label": "Monthly Active Users",
                        "description": "MAU from Looker",
                        "synonyms": ["MAU"],
                        "metadata": {
                            "grain": "monthly",
                            "unit": "count",
                            "direction": "higher_is_better",
                        },
                        "aggregation": "COUNT(DISTINCT user_id)",
                    },
                    {
                        "name": "plan_tier",
                        "type": "dimension",
                        "label": "Plan Tier",
                        "description": "Current subscription tier",
                        "abbreviations": ["tier"],
                    },
                ],
            }
        ],
        "looks": [
            {
                "id": 123,
                "title": "MAU Look",
                "metric_id": "monthly_active_users",
                "sql": (
                    "SELECT COUNT(DISTINCT user_id) AS monthly_active_users "
                    "FROM prod.product.user_activity"
                ),
                "tables": ["prod.product.user_activity"],
                "url": "https://looker.example/looks/123",
                "updated_at": "2026-04-16T02:00:00Z",
            }
        ],
    }

    def _open_url(request, timeout: float):
        requests.append((request, timeout))
        return _FakeResponse(payload)

    adapter = LookerAdapter(
        "https://looker.example/api",
        auth_token="secret-token",
        open_url=_open_url,
    )

    metrics = adapter.fetch_metrics(None)
    glossary = adapter.fetch_glossary_terms(None)
    queries = adapter.fetch_verified_queries(None)

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.metric_id == "monthly_active_users"
    assert metric.owner == "looker"
    assert metric.calculation.numerator.source == "prod.product.user_activity"
    assert "MAU" in metric.synonyms
    assert len(glossary) == 2
    metric_term = next(term for term in glossary if term.term_id == "term.monthly_active_users")
    dimension_term = next(term for term in glossary if term.term_id == "term.plan_tier")
    assert metric_term.category == "metric"
    assert metric_term.linked_metric_ids == ["monthly_active_users"]
    assert dimension_term.category == "dimension"
    assert len(queries) == 1
    query = queries[0]
    assert query.vq_id == "look-123"
    assert query.metric_id == "monthly_active_users"
    assert query.tags == ["looker"]
    request, timeout = requests[0]
    assert request.full_url == "https://looker.example/api"
    assert request.get_header("Authorization") == "token secret-token"
    assert timeout == 15.0


def test_looker_adapter_filters_old_fields_and_looks_by_since() -> None:
    payload = {
        "views": [
            {
                "name": "user_activity",
                "fields": [
                    {
                        "name": "daily_active_users",
                        "type": "measure",
                        "description": "DAU from Looker",
                        "aggregation": "COUNT(DISTINCT user_id)",
                        "updated_at": "2026-03-01T00:00:00Z",
                    }
                ],
            }
        ],
        "looks": [
            {
                "id": 7,
                "sql": "SELECT 1",
                "updated_at": "2026-03-01T00:00:00Z",
            }
        ],
    }
    adapter = LookerAdapter(
        "https://looker.example/api",
        open_url=lambda request, timeout: _FakeResponse(payload),
    )

    since = datetime(2026, 4, 1, tzinfo=UTC)

    assert adapter.fetch_metrics(since) == []
    assert adapter.fetch_glossary_terms(since) == []
    assert adapter.fetch_verified_queries(since) == []
