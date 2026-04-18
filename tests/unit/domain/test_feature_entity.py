from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ds_agent.domain.entities.feature import Feature, FeatureStatistics


def _feature_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "feature_id": "f_user_activity_30d",
        "display_name": "User Activity 30d",
        "version": 1,
        "description": "Rolling 30 day user activity score.",
        "transformation_logic": "SELECT user_id, COUNT(*) AS activity_30d FROM growth.user_logins",
        "source_tables": ["growth.user_logins"],
        "owner": "growth-ds",
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "statistics": FeatureStatistics(
            mean=1.4,
            median=1.0,
            p95=4.0,
            null_rate=0.02,
            distinct_count=120,
            last_computed_at=datetime(2026, 4, 16, tzinfo=UTC),
        ),
        "point_in_time_safe": True,
        "alias": "experimental",
        "used_in_experiments": ["exp_churn_001"],
        "tags": ["churn"],
    }
    payload.update(overrides)
    return payload


def test_feature_normalizes_string_lists_case_insensitively() -> None:
    feature = Feature.model_validate(
        _feature_payload(
            source_tables=[
                "growth.user_logins",
                " growth.user_logins ",
                "growth.user_sessions",
            ],
            used_in_experiments=["exp_churn_001", " exp_churn_001 ", "exp_churn_002"],
            tags=["churn", " CHURN ", "retention"],
        )
    )

    assert feature.source_tables == ["growth.user_logins", "growth.user_sessions"]
    assert feature.used_in_experiments == ["exp_churn_001", "exp_churn_002"]
    assert feature.tags == ["churn", "retention"]
    assert feature.ref().feature_id == "f_user_activity_30d"
    assert feature.ref().version == 1


def test_feature_requires_at_least_one_source_table() -> None:
    with pytest.raises(ValidationError):
        Feature.model_validate(_feature_payload(source_tables=[]))
