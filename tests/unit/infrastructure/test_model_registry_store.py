from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.model import Model
from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore


def _model(version: int, alias: str = "challenger", **overrides: object) -> Model:
    payload: dict[str, object] = {
        "model_id": "m_churn_lightgbm",
        "version": version,
        "alias": alias,
        "lineage_run_id": f"run-{version}",
        "artifact": {
            "uri": f"model://churn/lightgbm/v{version}",
            "format": "json",
            "size_bytes": 1024 * version,
            "checksum": f"checksum-{version}",
        },
        "serving": {
            "runtime": "batch",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
        },
        "created_at": datetime(2026, 4, 16, tzinfo=UTC),
        "description": f"Model version {version}",
    }
    payload.update(overrides)
    return Model.model_validate(payload)


def test_sqlite_model_registry_store_round_trips_and_supports_alias_lookup(tmp_path) -> None:
    store = SqliteModelRegistryStore(tmp_path / "model_registry.db")
    challenger = _model(1, alias="challenger", lineage_run_id="run-a")
    retired = _model(2, alias="retired", lineage_run_id="run-a")

    store.save(challenger)
    store.save(retired)

    loaded = store.get("m_churn_lightgbm", 1)
    assert loaded is not None
    assert loaded.alias == "challenger"

    alias_loaded = store.get_by_alias("challenger")
    assert alias_loaded is not None
    assert alias_loaded.version == 1

    from_run = store.list_from_run("run-a")
    assert [model.version for model in from_run] == [2, 1]


def test_sqlite_model_registry_store_enforces_active_alias_uniqueness(tmp_path) -> None:
    store = SqliteModelRegistryStore(tmp_path / "model_registry.db")
    champion = _model(1, alias="champion")
    another_champion = _model(
        1,
        alias="champion",
        model_id="m_churn_xgboost",
        lineage_run_id="run-b",
        artifact={
            "uri": "model://churn/xgboost/v1",
            "format": "json",
            "size_bytes": 2048,
            "checksum": "checksum-xgb",
        },
    )

    store.save(champion)

    with pytest.raises(ValueError):
        store.save(another_champion)
