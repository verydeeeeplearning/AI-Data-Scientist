from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ds_agent.memory.semantic.domain.metric import Metric


def _metric_payload() -> dict[str, object]:
    return {
        "metric_id": "monthly_churn_rate",
        "display_name": "월간 이탈률",
        "owner": "growth_team",
        "definition": "당월 해지자 수 / 전월 말 활성 구독자 수",
        "synonyms": [" churn ", "이탈률", "Churn", ""],
        "grain": "monthly",
        "unit": "ratio",
        "direction": "lower_is_better",
        "typical_range": (0.02, 0.08),
        "calculation": {
            "numerator": {
                "source": "prod.growth.subscription",
                "filter": "event_type = 'cancel'",
                "aggregation": "COUNT(DISTINCT user_id)",
            },
            "denominator": {
                "source": "prod.growth.subscription",
                "filter": "status = 'active'",
                "aggregation": "COUNT(DISTINCT user_id)",
            },
        },
        "related_metrics": ["retention_30d", "retention_30d", "ltv"],
        "approved_by": [
            {
                "team": "growth_team",
                "decision_date": date(2026, 3, 1),
                "decision_id": "DL-1",
            }
        ],
        "caveats": ["프로모션 기간 중 일시 하락", "프로모션 기간 중 일시 하락"],
        "verified_query_ids": ["vq_churn_001", "vq_churn_001"],
    }


def test_metric_normalizes_string_lists() -> None:
    metric = Metric(**_metric_payload())

    assert metric.synonyms == ["churn", "이탈률"]
    assert metric.related_metrics == ["retention_30d", "ltv"]
    assert metric.caveats == ["프로모션 기간 중 일시 하락"]
    assert metric.verified_query_ids == ["vq_churn_001"]


def test_metric_rejects_descending_typical_range() -> None:
    payload = _metric_payload()
    payload["typical_range"] = (0.09, 0.01)

    with pytest.raises(ValidationError, match="typical_range"):
        Metric(**payload)


def test_metric_requires_version_at_least_one() -> None:
    payload = _metric_payload()
    payload["version"] = 0

    with pytest.raises(ValidationError):
        Metric(**payload)
