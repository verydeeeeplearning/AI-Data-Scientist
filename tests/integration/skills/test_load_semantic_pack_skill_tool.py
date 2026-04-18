from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.infrastructure.yaml_metric_loader import YamlMetricLoader
from ds_agent.tools._semantic_common import set_semantic_memory_container
from ds_agent.tools.path_utils import set_active_workspace
from ds_agent.tools.registry import ToolRegistry


def _load_modules() -> None:
    importlib.import_module("ds_agent.tools.load_semantic_pack")


def _write_pack(
    pack_dir: Path,
    metric_yaml: str,
    *,
    schema_version: int = 6,
    checksum: str | None = None,
) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
    lines = [
        "pack_id: acme_corp_2026_q2",
        'display_name: "ACME Corp Semantic Pack (2026 Q2)"',
        "owner: data_platform_team",
        "version: 1.3.0",
        f"requires_semantic_layer_schema_version: {schema_version}",
    ]
    if checksum is not None:
        lines.append(f'checksum: "{checksum}"')
    (pack_dir / "pack.yaml").write_text("\n".join(lines), encoding="utf-8")
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(metric_yaml, encoding="utf-8")


def _metric_yaml(*, definition: str = "Monthly customer churn rate") -> str:
    return "\n".join(
        [
            "metric_id: monthly_churn_rate",
            "display_name: Monthly Churn Rate",
            "owner: growth_team",
            f'definition: "{definition}"',
            "synonyms:",
            "  - customer churn",
            "grain: monthly",
            "unit: ratio",
            "direction: lower_is_better",
            "calculation:",
            "  numerator:",
            "    source: prod.growth.subscription",
            "    filter: event_type = 'cancel'",
            "    aggregation: COUNT(*)",
            "  denominator:",
            "    source: prod.growth.subscription",
            "    filter: status = 'active'",
            "    aggregation: COUNT(*)",
        ]
    )


@pytest.fixture(autouse=True)
def _reset_runtime():
    set_active_workspace(None)
    set_semantic_memory_container(None)
    yield
    set_active_workspace(None)
    set_semantic_memory_container(None)


@pytest.mark.asyncio
async def test_load_semantic_pack_tool_supports_dry_run_and_apply(tmp_path) -> None:
    _load_modules()
    set_active_workspace(tmp_path)
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    set_semantic_memory_container(container)
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml())
    checksum = YamlMetricLoader().compute_pack_checksum(pack_dir)
    _write_pack(pack_dir, _metric_yaml(), checksum=checksum)

    dry_run = json.loads(
        await ToolRegistry.dispatch(
            "load_semantic_pack",
            {"pack_dir": "acme-pack", "dry_run": True},
        )
    )
    applied = json.loads(
        await ToolRegistry.dispatch(
            "load_semantic_pack",
            {"pack_dir": "acme-pack", "dry_run": False},
        )
    )

    assert dry_run["metric_diffs"][0]["status"] == "add"
    assert applied["applied_metric_ids"] == ["monthly_churn_rate"]
    assert container.metrics.get("monthly_churn_rate") is not None


@pytest.mark.asyncio
async def test_load_semantic_pack_tool_rejects_checksum_mismatch(tmp_path) -> None:
    _load_modules()
    set_active_workspace(tmp_path)
    set_semantic_memory_container(
        build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    )
    pack_dir = tmp_path / "acme-pack"
    _write_pack(pack_dir, _metric_yaml(), checksum="sha256:deadbeef")

    payload = json.loads(
        await ToolRegistry.dispatch(
            "load_semantic_pack",
            {"pack_dir": "acme-pack"},
        )
    )

    assert "error" in payload
    assert "checksum mismatch" in payload["error"]


@pytest.mark.asyncio
async def test_load_semantic_pack_tool_loads_builtin_skill_pack(tmp_path) -> None:
    _load_modules()
    set_active_workspace(tmp_path)
    container = build_semantic_memory_container(db_path=str(tmp_path / "semantic.sqlite3"))
    set_semantic_memory_container(container)

    payload = json.loads(
        await ToolRegistry.dispatch(
            "load_semantic_pack",
            {"skill_name": "domain-pack-enterprise", "dry_run": True},
        )
    )

    assert payload["source"] == "skill"
    assert payload["skill_name"] == "domain-pack-enterprise"
    assert payload["pack_id"] == "domain_pack_enterprise"
    assert len(payload["metric_diffs"]) >= 10
    assert len(payload["glossary_diffs"]) >= 30
    assert len(payload["trust_diffs"]) >= 20
    assert len(payload["verified_query_diffs"]) >= 15
    assert {item["metric_id"] for item in payload["metric_diffs"]} >= {
        "monthly_churn_rate",
        "monthly_active_users",
        "lifetime_value",
    }
