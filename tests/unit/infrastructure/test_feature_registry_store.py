from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.feature import Feature, FeatureStatistics
from ds_agent.domain.errors.feature_registry_errors import FeatureVersionConflictError
from ds_agent.infrastructure.persistence.feature_registry_store import SqliteFeatureRegistryStore


def _feature(version: int = 1, **overrides: object) -> Feature:
    payload: dict[str, object] = {
        "feature_id": "f_user_activity_30d",
        "display_name": "User Activity 30d",
        "version": version,
        "description": "Rolling 30 day user activity score.",
        "transformation_logic": "SELECT * FROM growth.user_logins",
        "source_tables": ["growth.user_logins"],
        "owner": "growth-ds",
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "statistics": FeatureStatistics(
            mean=1.2,
            median=1.0,
            p95=2.5,
            null_rate=0.01,
            distinct_count=50,
            last_computed_at=datetime(2026, 4, 16, tzinfo=UTC),
        ),
        "point_in_time_safe": True,
        "alias": "experimental",
        "used_in_experiments": ["exp_churn_001"],
        "tags": ["churn"],
    }
    payload.update(overrides)
    return Feature.model_validate(payload)


def test_sqlite_feature_registry_store_round_trips_and_supports_reverse_lookups(
    tmp_path,
) -> None:
    db_path = tmp_path / "feature_registry.db"
    store = SqliteFeatureRegistryStore(db_path)
    feature_v1 = _feature(version=1)
    feature_v2 = _feature(
        version=2,
        alias="stable",
        source_tables=["growth.user_logins", "growth.user_sessions"],
        used_in_experiments=["exp_churn_002"],
    )

    store.save(feature_v1)
    store.save(feature_v2)

    latest = store.get_latest("f_user_activity_30d")
    assert latest is not None
    assert latest.version == 2
    assert latest.alias == "stable"

    versions = store.list_versions("f_user_activity_30d")
    assert [feature.version for feature in versions] == [2, 1]

    by_source = store.list_by_source_table("growth.user_sessions")
    assert [feature.version for feature in by_source] == [2]

    experiments = store.list_experiments_using("f_user_activity_30d")
    assert experiments == ["exp_churn_002", "exp_churn_001"]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT alias FROM feature_alias_history WHERE feature_id = ? ORDER BY version",
            ("f_user_activity_30d",),
        ).fetchall()
    assert [row[0] for row in rows] == ["experimental", "stable"]


def test_sqlite_feature_registry_store_rejects_duplicate_version(tmp_path) -> None:
    store = SqliteFeatureRegistryStore(tmp_path / "feature_registry.db")
    feature = _feature(version=1)

    store.save(feature)

    with pytest.raises(FeatureVersionConflictError):
        store.save(feature)
