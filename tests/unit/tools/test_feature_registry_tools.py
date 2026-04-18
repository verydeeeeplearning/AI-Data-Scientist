from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass

import pytest
import yaml

from ds_agent.infrastructure.feature_registry_container import build_feature_registry_container
from ds_agent.infrastructure.persistence.feature_registry_store import SqliteFeatureRegistryStore
from ds_agent.tools.registry import ToolRegistry


@dataclass
class StaticSourceTableCatalog:
    known_tables: set[str]

    def exists(self, fqtn: str) -> bool:
        return fqtn in self.known_tables


@pytest.fixture
def feature_registry_tool_module(tmp_path):
    ToolRegistry.reset()
    module_name = "ds_agent.tools.feature_registry_tools"
    if module_name in sys.modules:
        module = importlib.reload(sys.modules[module_name])
    else:
        module = importlib.import_module(module_name)

    store = SqliteFeatureRegistryStore(tmp_path / "feature_registry.db")
    container = build_feature_registry_container(
        store=store,
        source_tables=StaticSourceTableCatalog({"growth.user_logins"}),
    )
    module.set_feature_registry_container(container)
    return module


@pytest.mark.asyncio
async def test_register_feature_tool_happy_path(tmp_path, feature_registry_tool_module) -> None:
    yaml_path = tmp_path / "f_user_activity_30d.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "feature_id": "f_user_activity_30d",
                "display_name": "User Activity 30d",
                "version": 1,
                "description": "Rolling 30 day user activity score.",
                "transformation_logic": "SELECT * FROM growth.user_logins",
                "source_tables": ["growth.user_logins"],
                "owner": "growth-ds",
                "created_at": "2026-04-16T00:00:00+00:00",
                "statistics": {
                    "mean": 1.2,
                    "median": 1.0,
                    "p95": 2.5,
                    "null_rate": 0.01,
                    "distinct_count": 50,
                    "last_computed_at": "2026-04-16T00:00:00+00:00",
                },
                "point_in_time_safe": True,
                "alias": "experimental",
                "used_in_experiments": [],
                "tags": ["churn"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = json.loads(
        await ToolRegistry.dispatch("register_feature", {"yaml_uri": str(yaml_path)})
    )

    assert result["ok"] is True
    assert result["feature_id"] == "f_user_activity_30d"
    assert result["version"] == 1


@pytest.mark.asyncio
async def test_register_feature_tool_returns_source_table_error(
    tmp_path,
    feature_registry_tool_module,
) -> None:
    yaml_path = tmp_path / "unknown_feature.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "feature_id": "f_unknown",
                "display_name": "Unknown",
                "version": 1,
                "description": "Unknown source table.",
                "transformation_logic": "SELECT * FROM growth.unknown",
                "source_tables": ["growth.unknown"],
                "owner": "growth-ds",
                "created_at": "2026-04-16T00:00:00+00:00",
                "statistics": {"last_computed_at": "2026-04-16T00:00:00+00:00"},
                "point_in_time_safe": True,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = json.loads(
        await ToolRegistry.dispatch("register_feature", {"yaml_uri": str(yaml_path)})
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "UNKNOWN_SOURCE_TABLE"
