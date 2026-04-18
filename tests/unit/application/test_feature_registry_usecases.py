from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.application.services.feature_registry_usecases import RegisterFeatureUseCase
from ds_agent.domain.entities.feature import Feature, FeatureStatistics
from ds_agent.domain.errors.feature_registry_errors import (
    FeatureVersionConflictError,
    UnknownSourceTableError,
)
from ds_agent.domain.interfaces.feature_registry import FeatureRegistryStore


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
        "used_in_experiments": [],
        "tags": ["churn"],
    }
    payload.update(overrides)
    return Feature.model_validate(payload)


class InMemoryFeatureRegistryStore(FeatureRegistryStore):
    def __init__(self) -> None:
        self._features: dict[tuple[str, int], Feature] = {}

    def get(self, feature_id: str, version: int) -> Feature | None:
        feature = self._features.get((feature_id, version))
        return feature.model_copy(deep=True) if feature is not None else None

    def get_latest(self, feature_id: str) -> Feature | None:
        matches = [feature for (fid, _), feature in self._features.items() if fid == feature_id]
        if not matches:
            return None
        latest = max(matches, key=lambda feature: feature.version)
        return latest.model_copy(deep=True)

    def list_versions(self, feature_id: str) -> list[Feature]:
        matches = [feature for (fid, _), feature in self._features.items() if fid == feature_id]
        ordered = sorted(matches, key=lambda item: item.version, reverse=True)
        return [feature.model_copy(deep=True) for feature in ordered]

    def list_features(self, *, alias=None, limit: int = 100) -> list[Feature]:
        latest_by_id: dict[str, Feature] = {}
        for feature in self._features.values():
            current = latest_by_id.get(feature.feature_id)
            if current is None or feature.version > current.version:
                latest_by_id[feature.feature_id] = feature
        values = [
            feature.model_copy(deep=True)
            for feature in latest_by_id.values()
            if alias is None or feature.alias == alias
        ]
        values.sort(key=lambda feature: feature.feature_id)
        return values[:limit]

    def save(self, feature: Feature) -> None:
        self._features[(feature.feature_id, feature.version)] = feature.model_copy(deep=True)

    def list_experiments_using(self, feature_id: str) -> list[str]:
        seen: set[str] = set()
        experiments: list[str] = []
        for feature in self.list_versions(feature_id):
            for experiment_id in feature.used_in_experiments:
                if experiment_id in seen:
                    continue
                seen.add(experiment_id)
                experiments.append(experiment_id)
        return experiments

    def list_by_source_table(self, source_table: str) -> list[Feature]:
        matches = [
            feature.model_copy(deep=True)
            for feature in self._features.values()
            if source_table in feature.source_tables
        ]
        matches.sort(key=lambda feature: (feature.feature_id, -feature.version))
        return matches


@dataclass
class StubLoader:
    feature: Feature

    def load(self, source: str | Path) -> Feature:
        return self.feature.model_copy(deep=True)


@dataclass
class StaticSourceTableCatalog:
    known_tables: set[str]

    def exists(self, fqtn: str) -> bool:
        return fqtn in self.known_tables


def test_register_feature_persists_new_version_and_returns_warnings() -> None:
    store = InMemoryFeatureRegistryStore()
    feature = _feature(
        point_in_time_safe=False,
        alias="deprecated",
    )
    use_case = RegisterFeatureUseCase(
        store,
        StubLoader(feature),
        StaticSourceTableCatalog({"growth.user_logins"}),
    )

    result = use_case.execute("registry/features/f_user_activity_30d.yaml")

    assert result.feature_id == "f_user_activity_30d"
    assert result.version == 1
    assert len(result.validation_warnings) == 2
    assert store.get("f_user_activity_30d", 1) is not None


def test_register_feature_rejects_unknown_source_table() -> None:
    use_case = RegisterFeatureUseCase(
        InMemoryFeatureRegistryStore(),
        StubLoader(_feature(source_tables=["growth.unknown_table"])),
        StaticSourceTableCatalog({"growth.user_logins"}),
    )

    with pytest.raises(UnknownSourceTableError):
        use_case.execute("feature.yaml")


def test_register_feature_rejects_duplicate_or_regressed_version() -> None:
    store = InMemoryFeatureRegistryStore()
    existing = _feature(version=2)
    store.save(existing)

    duplicate = RegisterFeatureUseCase(
        store,
        StubLoader(existing),
        StaticSourceTableCatalog({"growth.user_logins"}),
    )
    with pytest.raises(FeatureVersionConflictError):
        duplicate.execute("feature.yaml")

    regressed = RegisterFeatureUseCase(
        store,
        StubLoader(_feature(version=1)),
        StaticSourceTableCatalog({"growth.user_logins"}),
    )
    with pytest.raises(FeatureVersionConflictError):
        regressed.execute("feature.yaml")
