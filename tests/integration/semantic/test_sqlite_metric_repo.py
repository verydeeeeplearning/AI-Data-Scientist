from __future__ import annotations

import uuid
from pathlib import Path

from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.infrastructure.sqlite_base import SemanticSqliteDatabase
from ds_agent.memory.semantic.infrastructure.sqlite_metric_repo import SqliteMetricRepository


def _db() -> SemanticSqliteDatabase:
    base_dir = Path("semantic_test_artifacts/metric")
    base_dir.mkdir(parents=True, exist_ok=True)
    return SemanticSqliteDatabase(base_dir / f"{uuid.uuid4().hex}.db")


def _metric() -> Metric:
    return Metric(
        metric_id="monthly_churn_rate",
        display_name="월간 이탈률",
        owner="growth_team",
        definition="당월 해지자 / 전월 말 활성 구독자",
        synonyms=["churn", "해지율"],
        grain="monthly",
        unit="ratio",
        direction="lower_is_better",
        calculation={
            "numerator": {
                "source": "prod.growth.subscription",
                "filter": "event_type = 'cancel'",
                "aggregation": "COUNT(DISTINCT user_id)",
            }
        },
        verified_query_ids=["vq_churn_001"],
    )


def test_metric_repo_round_trip_and_synonym_lookup() -> None:
    repo = SqliteMetricRepository(_db())
    metric = _metric()
    repo.save(metric)

    restored = repo.get(metric.metric_id)
    assert restored is not None
    assert restored.metric_id == metric.metric_id
    assert restored.synonyms == ["churn", "해지율"]

    matches = repo.resolve("해지율")
    assert [item.metric_id for item in matches] == [metric.metric_id]

