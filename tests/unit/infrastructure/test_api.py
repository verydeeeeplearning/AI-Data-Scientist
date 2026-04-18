"""Tests for the FastAPI backend (Plan 07 Phase 1).

Covers:
- WebSocket RPC protocol (req/res frames)
- WsAgentCallbacks event emission
- HTTP routes (/api/status, /api/config, /api/files)
- AppState management
"""

from __future__ import annotations

import asyncio
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.auth import AuthProfile, OAuthTokenSet
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

starlette = pytest.importorskip("starlette", reason="starlette not installed")
from starlette.websockets import WebSocketDisconnect, WebSocketState  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_ws():
    """Create a mock WebSocket that records sent JSON frames."""
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.sent: list[dict] = []

    async def _send_json(data: dict) -> None:
        ws.sent.append(data)

    ws.send_json = AsyncMock(side_effect=_send_json)
    return ws


@pytest.fixture()
def app_state(tmp_path):
    """Create an AppState with a temp workspace."""
    from ds_agent.api.ws_handler import AppState
    from ds_agent.config.schema import AgentConfig, DSAgentConfig

    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    return AppState(config=config)


@pytest.fixture()
def rpc_handler(app_state, mock_ws):
    from ds_agent.api.ws_handler import WsRpcHandler

    return WsRpcHandler(state=app_state, websocket=mock_ws)


def _seed_semantic_state(app_state) -> None:
    from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
    from ds_agent.memory.semantic.domain.metric import Metric
    from ds_agent.memory.semantic.domain.trust import TableTrust
    from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

    container = app_state._get_semantic_memory_container()
    container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "monthly_churn_rate",
                "display_name": "Monthly Churn Rate",
                "owner": "growth_team",
                "definition": "Monthly customer churn rate",
                "synonyms": ["customer churn"],
                "grain": "monthly",
                "unit": "ratio",
                "direction": "lower_is_better",
                "verified_query_ids": ["vq-monthly-churn-postgres"],
                "calculation": {
                    "numerator": {
                        "source": "prod.growth.subscription",
                        "filter": "event_type = 'cancel'",
                        "aggregation": "COUNT(*)",
                    },
                    "denominator": {
                        "source": "prod.growth.subscription",
                        "filter": "status = 'active'",
                        "aggregation": "COUNT(*)",
                    },
                },
            }
        )
    )
    container.glossary.save(
        GlossaryTerm.model_validate(
            {
                "term_id": "term.churn",
                "canonical_form": "churn",
                "definition": "Customer churn metric.",
                "linked_metric_ids": ["monthly_churn_rate"],
                "category": "metric",
                "owner": "growth_team",
            }
        )
    )
    container.trust.save(
        TableTrust.model_validate(
            {
                "fqtn": "prod.growth.subscription",
                "grade": "gold",
                "owner": "growth_team",
                "description": "Subscription fact table",
                "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                "grade_rationale": "Certified by analytics engineering",
                "last_audited": "2026-04-15",
            }
        )
    )
    container.verified_queries.save(
        VerifiedQuery.model_validate(
            {
                "vq_id": "vq-monthly-churn-postgres",
                "metric_id": "monthly_churn_rate",
                "dialect": "postgres",
                "description": "Verified monthly churn query",
                "sql_template": "SELECT 0.05 AS monthly_churn_rate",
                "referenced_tables": ["prod.growth.subscription"],
                "verified_by": "reviewer@corp.example",
                "last_verified": "2026-04-15",
                "verification_evidence": "Dashboard parity",
            }
        )
    )


def _seed_runtime_semantic_state(app_state) -> None:
    from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
    from ds_agent.infrastructure.semantic_memory_runtime import resolve_semantic_db_path
    from ds_agent.memory.semantic.domain.metric import Metric

    container = build_semantic_memory_container(
        workspace_dir=app_state.config.agent.workspace_dir,
        db_path=str(resolve_semantic_db_path(app_state.config.agent.workspace_dir)),
    )
    container.metrics.save(
        Metric.model_validate(
            {
                "metric_id": "net_revenue_retention",
                "display_name": "Net Revenue Retention",
                "owner": "finance_team",
                "definition": "Monthly NRR percentage",
                "synonyms": ["nrr"],
                "grain": "monthly",
                "unit": "percentage",
                "direction": "higher_is_better",
                "calculation": {
                    "numerator": {
                        "source": "prod.finance.account_monthly",
                        "filter": "period_state = 'closed'",
                        "aggregation": "SUM(expansion_mrr)",
                    },
                    "denominator": {
                        "source": "prod.finance.account_monthly",
                        "filter": "period_state = 'closed'",
                        "aggregation": "SUM(starting_mrr)",
                    },
                },
            }
        )
    )


def _write_semantic_pack(pack_dir: Path) -> None:
    (pack_dir / "metrics").mkdir(parents=True, exist_ok=True)
    (pack_dir / "glossary").mkdir(parents=True, exist_ok=True)
    (pack_dir / "trust").mkdir(parents=True, exist_ok=True)
    (pack_dir / "verified_queries").mkdir(parents=True, exist_ok=True)
    (pack_dir / "pack.yaml").write_text(
        "\n".join(
            [
                "pack_id: acme_pack",
                'display_name: "ACME Pack"',
                "owner: data_platform_team",
                "version: 1.0.0",
                "requires_semantic_layer_schema_version: 6",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "metrics" / "monthly_churn_rate.yaml").write_text(
        "\n".join(
            [
                "metric_id: monthly_churn_rate",
                "display_name: Monthly Churn Rate",
                "owner: growth_team",
                'definition: "Monthly customer churn rate"',
                "synonyms:",
                "  - customer churn",
                "grain: monthly",
                "unit: ratio",
                "direction: lower_is_better",
                "verified_query_ids:",
                "  - vq-monthly-churn-postgres",
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
        ),
        encoding="utf-8",
    )
    (pack_dir / "glossary" / "churn.yaml").write_text(
        "\n".join(
            [
                "term_id: term.churn",
                "canonical_form: churn",
                'definition: "Customer churn metric."',
                "linked_metric_ids:",
                "  - monthly_churn_rate",
                "category: metric",
                "owner: growth_team",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "trust" / "subscription.yaml").write_text(
        "\n".join(
            [
                "fqtn: prod.growth.subscription",
                "grade: gold",
                "owner: growth_team",
                'description: "Subscription fact table"',
                "refresh:",
                "  cadence: daily",
                "  max_staleness_minutes: 1440",
                'grade_rationale: "Certified by analytics engineering"',
                "last_audited: 2026-04-15",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "verified_queries" / "vq-monthly-churn-postgres.sql").write_text(
        "\n".join(
            [
                "---",
                "vq_id: vq-monthly-churn-postgres",
                "metric_id: monthly_churn_rate",
                "dialect: postgres",
                "description: Verified churn query",
                "referenced_tables:",
                "  - prod.growth.subscription",
                "verified_by: reviewer@corp.example",
                "last_verified: 2026-04-15",
                "verification_evidence: Dashboard parity",
                "---",
                "SELECT 0.05 AS monthly_churn_rate;",
            ]
        ),
        encoding="utf-8",
    )


def _seed_decision_os_state(app_state) -> dict[str, str]:
    from datetime import UTC, datetime

    from ds_agent.domain.entities.experiment import ExperimentRun
    from ds_agent.domain.entities.feature import Feature, FeatureStatistics
    from ds_agent.domain.entities.model import Model
    from ds_agent.domain.entities.post_deploy import PostDeployMonitorState
    from ds_agent.domain.entities.review_artifact import build_review_artifact
    from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
        SqliteDeployMonitorStateStore,
    )
    from ds_agent.infrastructure.persistence.feature_registry_store import (
        SqliteFeatureRegistryStore,
    )
    from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
    from ds_agent.memory.experiment_log import ExperimentLog

    workspace = Path(app_state.config.agent.workspace_dir)
    experiment_log = ExperimentLog(data_dir=str(workspace / "data" / "memory" / "experiment_log"))
    experiment_log.record_extended(
        ExperimentRun.model_validate(
            {
                "run_id": "run-champion",
                "experiment_group": "exp_churn",
                "sequence": 1,
                "hypothesis": {
                    "statement": "Champion baseline",
                    "rationale": "Current production baseline.",
                    "expected_effect": "F1 improves.",
                },
                "method": {
                    "model_family": "lightgbm",
                    "hyperparameters": {"learning_rate": 0.05},
                    "random_seed": 42,
                    "code_ref": "git:aaa111",
                },
                "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
                "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-07",
                "result": {"metrics": {"f1_macro": 0.80, "fp_rate": 0.12}},
                "verifier_summary": {
                    "statistical": "PASS",
                    "data": "PASS",
                    "policy": "PASS",
                },
                "created_at": datetime(2026, 4, 16, 9, tzinfo=UTC),
                "owner": "growth-ds",
                "status": "succeeded",
                "promotion_state": "production",
                "reproducibility_status": "reproduced",
            }
        )
    )
    experiment_log.record_extended(
        ExperimentRun.model_validate(
            {
                "run_id": "run-candidate",
                "experiment_group": "exp_churn",
                "sequence": 2,
                "hypothesis": {
                    "statement": "Candidate uplift",
                    "rationale": "Tune the learning rate and feature version.",
                    "expected_effect": "F1 improves.",
                },
                "method": {
                    "model_family": "lightgbm",
                    "hyperparameters": {"learning_rate": 0.08},
                    "random_seed": 42,
                    "code_ref": "git:bbb222",
                },
                "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 2}],
                "data_snapshot_uri": "snapshot://warehouse/churn/2026-04-14",
                "result": {"metrics": {"f1_macro": 0.84, "fp_rate": 0.10}},
                "verifier_summary": {
                    "statistical": "PASS",
                    "data": "PASS",
                    "policy": "PASS",
                },
                "created_at": datetime(2026, 4, 16, 10, tzinfo=UTC),
                "owner": "growth-ds",
                "status": "succeeded",
                "promotion_state": "candidate",
                "reproducibility_status": "reproduced",
                "review_artifacts": [
                    build_review_artifact(
                        skill_name="retrain-vs-rollback",
                        summary="Rollback is safer than retrain for this candidate.",
                        artifact={
                            "recommendation": "rollback",
                            "rationale": (
                                "Observed drift and metric loss exceed rollback thresholds."
                            ),
                            "evidence": ["psi=0.33", "f1_macro=-0.14"],
                        },
                        narrative="Use the existing champion until retraining is complete.",
                    ).model_dump(mode="json")
                ],
            }
        )
    )

    feature_store = SqliteFeatureRegistryStore.for_workspace(str(workspace))
    for version, alias in ((1, "stable"), (2, "stable")):
        feature_store.save(
            Feature.model_validate(
                {
                    "feature_id": "f_user_activity_30d",
                    "display_name": "User Activity 30d",
                    "version": version,
                    "description": "Rolling 30 day user activity score.",
                    "transformation_logic": "SELECT * FROM growth.user_logins",
                    "source_tables": ["growth.user_logins"],
                    "owner": "growth-ds",
                    "created_at": datetime(2026, 4, 16, 8 + version, tzinfo=UTC),
                    "statistics": FeatureStatistics(
                        mean=1.2 + (0.1 * version),
                        median=1.0,
                        p95=2.5,
                        null_rate=0.01,
                        distinct_count=50,
                        last_computed_at=datetime(2026, 4, 16, 8 + version, tzinfo=UTC),
                    ),
                    "point_in_time_safe": True,
                    "alias": alias,
                }
            )
        )

    model_store = SqliteModelRegistryStore.for_workspace(str(workspace))
    model_store.save(
        Model.model_validate(
            {
                "model_id": "m_churn_lightgbm",
                "version": 5,
                "alias": "champion",
                "lineage_run_id": "run-champion",
                "artifact": {
                    "uri": "model://churn/lightgbm/v5",
                    "format": "json",
                    "size_bytes": 1024,
                    "checksum": "abc123",
                },
                "serving": {
                    "runtime": "batch",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 1}],
                    "latency_budget_ms": 100,
                    "throughput_budget_qps": 40,
                },
                "created_at": datetime(2026, 4, 16, 9, tzinfo=UTC),
                "description": "Champion churn model.",
            }
        )
    )
    model_store.save(
        Model.model_validate(
            {
                "model_id": "m_churn_candidate",
                "version": 6,
                "alias": "challenger",
                "lineage_run_id": "run-candidate",
                "artifact": {
                    "uri": "model://churn/lightgbm/v6",
                    "format": "json",
                    "size_bytes": 1200,
                    "checksum": "def456",
                },
                "serving": {
                    "runtime": "batch",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "feature_refs": [{"feature_id": "f_user_activity_30d", "version": 2}],
                    "latency_budget_ms": 100,
                    "throughput_budget_qps": 40,
                },
                "created_at": datetime(2026, 4, 16, 10, tzinfo=UTC),
                "description": "Candidate churn model.",
            }
        )
    )

    deploy_store = SqliteDeployMonitorStateStore.for_workspace(str(workspace))
    deploy_store.save(
        PostDeployMonitorState.model_validate(
            {
                "state_id": "deploy-001",
                "model_id": "m_churn_lightgbm",
                "model_version": 5,
                "alias": "champion",
                "window": "24h",
                "observed_at": datetime(2026, 4, 16, 12, tzinfo=UTC),
                "drift": {
                    "overall_status": "warning",
                    "max_psi": 0.33,
                    "max_ks": 0.41,
                    "top_drifting_features": ["f_user_activity_30d"],
                    "metrics": [],
                },
                "metrics": [
                    {
                        "metric": "f1_macro",
                        "baseline_value": 0.80,
                        "current_value": 0.66,
                        "delta": -0.14,
                        "direction": "worse",
                        "status": "alert",
                    }
                ],
                "service_level": {
                    "latency_p95_ms": 140.0,
                    "latency_budget_ms": 100,
                    "qps": 30.0,
                    "throughput_budget_qps": 40,
                    "status": "warning",
                },
                "remediation": {
                    "decision": "rollback",
                    "severity": "high",
                    "rationale": "Metric degradation and heavy drift.",
                    "should_alert": True,
                    "recommended_steps": ["Rollback champion."],
                },
                "overall_status": "alert",
                "alerts": ["Drift threshold exceeded"],
                "trigger_mode": "auto_rollback",
                "trigger_payload": {"executed": False},
            }
        )
    )

    rollback_plan = workspace / "registry" / "rollback" / "churn.yaml"
    rollback_plan.parent.mkdir(parents=True, exist_ok=True)
    rollback_plan.write_text(
        "\n".join(
            [
                "previous_champion_model_id: m_churn_lightgbm",
                "traffic_shift_procedure: Shift traffic back over 10 minutes.",
                "health_check_queries:",
                "  - SELECT 1",
                "estimated_rollback_time_sec: 600",
                "owner: mlops",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "rollback_plan_ref": "registry/rollback/churn.yaml",
        "workspace_dir": str(workspace),
        "candidate_model_id": "m_churn_candidate",
        "candidate_model_version": "6",
    }


# ---------------------------------------------------------------------------
# WsAgentCallbacks
# ---------------------------------------------------------------------------


class TestWsAgentCallbacks:
    """Test that callbacks emit correct WebSocket event frames."""

    async def test_on_tool_start(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.on_tool_start("data_loader", {"path": "data.csv"})

        assert len(mock_ws.sent) == 1
        frame = mock_ws.sent[0]
        assert frame["type"] == "event"
        assert frame["event"] == "tool.start"
        assert frame["payload"]["name"] == "data_loader"
        assert frame["payload"]["args"] == {"path": "data.csv"}

    async def test_on_tool_end(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.on_tool_end("data_loader", "loaded 100 rows", False)

        frame = mock_ws.sent[0]
        assert frame["event"] == "tool.end"
        assert frame["payload"]["success"] is True

    async def test_on_thinking(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.on_thinking("Let me analyze this...")

        frame = mock_ws.sent[0]
        assert frame["event"] == "thinking"
        assert frame["payload"]["text"] == "Let me analyze this..."

    async def test_on_stream_delta(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.on_stream_delta("Hello")

        frame = mock_ws.sent[0]
        assert frame["event"] == "stream.delta"
        assert frame["payload"]["token"] == "Hello"

    async def test_on_budget_warning(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks
        from ds_agent.domain.value_objects.budget import BudgetThresholdEvent

        cb = WsAgentCallbacks(mock_ws)
        event = BudgetThresholdEvent(
            dimension="cost",
            level="warning",
            used=8.0,
            limit=10.0,
            pct=80.0,
            message="cost budget warning (80%)",
        )
        await cb.on_budget_warning(event)

        frame = mock_ws.sent[0]
        assert frame["event"] == "budget.warning"
        assert frame["payload"]["dimension"] == "cost"
        assert frame["payload"]["pct"] == 80.0

    async def test_emit_stream_done(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.emit_stream_done("Analysis complete.", 0.05)

        frame = mock_ws.sent[0]
        assert frame["event"] == "stream.done"
        assert frame["payload"]["content"] == "Analysis complete."
        assert frame["payload"]["cost"] == 0.05

    async def test_skips_when_disconnected(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        mock_ws.client_state = WebSocketState.DISCONNECTED
        cb = WsAgentCallbacks(mock_ws)
        await cb.on_tool_start("test", {})

        assert len(mock_ws.sent) == 0

    async def test_on_step(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        await cb.on_step(3, "Step 3")

        frame = mock_ws.sent[0]
        assert frame["event"] == "status.update"
        assert frame["payload"]["step"] == 3


# ---------------------------------------------------------------------------
# WsRpcHandler — RPC protocol
# ---------------------------------------------------------------------------


class TestWsRpcHandler:
    """Test RPC request/response dispatch."""

    async def test_unknown_method(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "1",
                "method": "nonexistent.method",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["type"] == "res"
        assert frame["ok"] is False
        assert frame["error"]["code"] == "UNKNOWN_METHOD"

    async def test_invalid_type(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message({"type": "ping", "id": "1"})

        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert frame["error"]["code"] == "INVALID_TYPE"

    async def test_config_get(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cfg1",
                "method": "config.get",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["type"] == "res"
        assert frame["id"] == "cfg1"
        assert frame["ok"] is True
        assert "config" in frame["payload"]
        assert "provider" in frame["payload"]["config"]

    async def test_config_get_redacts_sensitive_fields(self, rpc_handler, mock_ws, app_state):
        app_state.config.oauth.gemini_client_secret = "super-secret"
        app_state.config.channels.telegram.bot_token = "12345:telegram-secret"

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cfg-redacted",
                "method": "config.get",
            }
        )

        frame = mock_ws.sent[0]
        config = frame["payload"]["config"]
        assert config["oauth"]["gemini_client_secret"] == "***REDACTED***"
        assert config["channels"]["telegram"]["bot_token"] == "***REDACTED***"

    async def test_config_set(self, rpc_handler, mock_ws, app_state):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cfg2",
                "method": "config.set",
                "params": {"path": "agent.mode", "value": "supervised"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert app_state.config.agent.mode == "supervised"

    async def test_config_set_autonomous_runtime_toggle(self, rpc_handler, mock_ws, app_state):
        with patch.object(app_state, "start_background_runtime", new=AsyncMock()) as start_runtime:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "cfg-auto-on",
                    "method": "config.set",
                    "params": {"path": "gateway.autonomous_runtime_enabled", "value": True},
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        start_runtime.assert_awaited_once_with(force=True)

        mock_ws.sent.clear()
        with patch.object(app_state, "stop_background_runtime", new=AsyncMock()) as stop_runtime:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "cfg-auto-off",
                    "method": "config.set",
                    "params": {"path": "gateway.autonomous_runtime_enabled", "value": False},
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        stop_runtime.assert_awaited_once()

    async def test_config_set_authority_overlay_sets_started_at(
        self, rpc_handler, mock_ws, app_state
    ):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cfg-overlay",
                "method": "config.set",
                "params": {"path": "gateway.authority_overlay", "value": "incident"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert app_state.config.gateway.authority_overlay == "incident"
        assert app_state.config.gateway.authority_overlay_started_at is not None

    async def test_config_set_workspace_dir_refreshes_file_listing(
        self, rpc_handler, mock_ws, app_state, tmp_path
    ):
        new_workspace = tmp_path / "workspace-2"
        new_workspace.mkdir()
        (new_workspace / "fresh.csv").write_text("a,b\n1,2", encoding="utf-8")

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cfg-ws",
                "method": "config.set",
                "params": {"path": "agent.workspace_dir", "value": str(new_workspace)},
            }
        )
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "files-ws",
                "method": "files.list",
            }
        )

        config_frame = mock_ws.sent[0]
        files_frame = mock_ws.sent[1]
        assert config_frame["ok"] is True
        assert files_frame["ok"] is True
        assert [f["name"] for f in files_frame["payload"]["files"]] == ["fresh.csv"]

    async def test_semantic_lookup_metric(self, rpc_handler, mock_ws, app_state):
        _seed_semantic_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-lookup",
                "method": "semantic.lookupMetric",
                "params": {"query": "customer churn"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        lookup = frame["payload"]["lookup"]
        assert lookup["query"] == "customer churn"
        assert lookup["matches"][0]["metric"]["metric_id"] == "monthly_churn_rate"
        assert lookup["glossaryMatches"][0]["term_id"] == "term.churn"

    async def test_semantic_lookup_metric_reads_runtime_semantic_db(
        self,
        rpc_handler,
        mock_ws,
        app_state,
    ):
        _seed_runtime_semantic_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-lookup-runtime",
                "method": "semantic.lookupMetric",
                "params": {"query": "nrr"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        lookup = frame["payload"]["lookup"]
        assert lookup["matches"][0]["metric"]["metric_id"] == "net_revenue_retention"

    async def test_semantic_get_trust(self, rpc_handler, mock_ws, app_state):
        _seed_semantic_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-trust",
                "method": "semantic.getTrust",
                "params": {"fqtns": ["prod.growth.subscription"]},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        trust = frame["payload"]["trust"]
        assert trust["action"] == "allow"
        assert trust["tables"][0]["fqtn"] == "prod.growth.subscription"
        assert trust["tables"][0]["grade"] == "gold"

    async def test_semantic_get_verified_query(self, rpc_handler, mock_ws, app_state):
        _seed_semantic_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-vq",
                "method": "semantic.getVerifiedQuery",
                "params": {"metricId": "monthly_churn_rate", "dialect": "postgres"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        verified_query = frame["payload"]["verifiedQuery"]
        assert verified_query["query"]["vq_id"] == "vq-monthly-churn-postgres"
        assert verified_query["rendered_sql"] == "SELECT 0.05 AS monthly_churn_rate"

    async def test_semantic_load_pack(self, rpc_handler, mock_ws, app_state):
        workspace_dir = Path(app_state.config.agent.workspace_dir)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        pack_dir = workspace_dir / "semantic-pack"
        _write_semantic_pack(pack_dir)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-pack",
                "method": "semantic.loadPack",
                "params": {
                    "packDir": str(pack_dir),
                    "dryRun": False,
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        load_pack = frame["payload"]["loadPack"]
        assert load_pack["pack_id"] == "acme_pack"
        assert load_pack["resolvedPackDir"] == str(pack_dir.resolve())
        assert load_pack["source"] == "workspace"
        assert load_pack["applied_metric_ids"] == ["monthly_churn_rate"]
        assert load_pack["applied_glossary_term_ids"] == ["term.churn"]
        assert load_pack["applied_table_ids"] == ["prod.growth.subscription"]
        assert load_pack["applied_verified_query_ids"] == ["vq-monthly-churn-postgres"]

    async def test_semantic_list_snapshots(self, rpc_handler, mock_ws, app_state):
        _seed_semantic_state(app_state)
        container = app_state._get_semantic_memory_container()
        container.snapshots.create(
            snapshot_id="semantic_snapshot-001",
            source_name="test",
            created_at=datetime(2026, 4, 16, 13, tzinfo=UTC),
            note="baseline semantic state",
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-snapshot-list",
                "method": "semantic.listSnapshots",
                "params": {"limit": 5},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        snapshot = frame["payload"]["snapshots"][0]
        assert snapshot["snapshot_id"] == "semantic_snapshot-001"
        assert snapshot["total_rows"] >= 4

    async def test_semantic_restore_snapshot(self, rpc_handler, mock_ws, app_state):
        _seed_semantic_state(app_state)
        container = app_state._get_semantic_memory_container()
        container.snapshots.create(
            snapshot_id="semantic_snapshot-restore",
            source_name="test",
            created_at=datetime(2026, 4, 16, 14, tzinfo=UTC),
            note="baseline semantic state",
        )
        container.metrics.save(
            Metric.model_validate(
                {
                    "metric_id": "monthly_churn_rate",
                    "display_name": "Monthly Churn Rate",
                    "owner": "growth_team",
                    "definition": "Updated churn definition",
                    "synonyms": ["gross churn"],
                    "grain": "monthly",
                    "unit": "ratio",
                    "direction": "lower_is_better",
                    "verified_query_ids": ["vq-monthly-churn-postgres"],
                    "calculation": {
                        "numerator": {
                            "source": "prod.growth.subscription",
                            "filter": "event_type = 'cancel'",
                            "aggregation": "COUNT(*)",
                        },
                        "denominator": {
                            "source": "prod.growth.subscription",
                            "filter": "status = 'active'",
                            "aggregation": "COUNT(*)",
                        },
                    },
                }
            )
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-snapshot-restore",
                "method": "semantic.restoreSnapshot",
                "params": {"snapshotId": "semantic_snapshot-restore"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        restored = frame["payload"]["restoreSnapshot"]
        assert restored["snapshot"]["snapshot_id"] == "semantic_snapshot-restore"
        assert "semantic_metric_synonym" in restored["restored_tables"]
        metric = app_state._get_semantic_memory_container().metrics.get("monthly_churn_rate")
        assert metric is not None
        assert metric.definition == "Monthly customer churn rate"

    async def test_semantic_sync_source_postgres(self, rpc_handler, mock_ws, app_state):
        from ds_agent.config.schema import WarehouseConnectorSettings
        from ds_agent.domain.value_objects.connector import ConnectorType

        app_state.config.connectors["analytics_prod"] = WarehouseConnectorSettings(
            type=ConnectorType.POSTGRES,
            label="Analytics Postgres",
            options={
                "host": "localhost",
                "database": "prod",
                "schema": "growth",
            },
        )
        app_state._connector_adapter_factory = lambda connector: _FakeSemanticWarehouseAdapter()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-sync",
                "method": "semantic.syncSource",
                "params": {
                    "sourceKind": "postgres",
                    "connectorName": "analytics_prod",
                    "dryRun": False,
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        sync = frame["payload"]["sync"]
        assert sync["source_name"] == "analytics_prod"
        assert sync["applied_table_ids"] == ["prod.growth.subscription"]
        assert sync["trust_diffs"][0]["status"] == "add"

    async def test_semantic_sync_source_snowflake(self, rpc_handler, mock_ws, app_state):
        from ds_agent.config.schema import WarehouseConnectorSettings
        from ds_agent.domain.value_objects.connector import ConnectorType

        app_state.config.connectors["warehouse_sf"] = WarehouseConnectorSettings(
            type=ConnectorType.SNOWFLAKE,
            label="Warehouse Snowflake",
            options={
                "account": "acme-account",
                "database": "ANALYTICS",
                "schema": "CURATED",
                "warehouse": "ANALYTICS_WH",
            },
        )
        app_state._connector_adapter_factory = lambda connector: (
            _FakeSnowflakeSemanticWarehouseAdapter()
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "semantic-sync-snowflake",
                "method": "semantic.syncSource",
                "params": {
                    "sourceKind": "snowflake",
                    "connectorName": "warehouse_sf",
                    "dryRun": False,
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        sync = frame["payload"]["sync"]
        assert sync["source_name"] == "warehouse_sf"
        assert sync["applied_table_ids"] == ["ANALYTICS.CURATED.ORDERS"]
        assert sync["trust_diffs"][0]["status"] == "add"

    async def test_semantic_sync_source_looker(self, rpc_handler, mock_ws, app_state):
        with patch(
            "ds_agent.memory.semantic.infrastructure.adapters.LookerAdapter",
            _FakeLookerSemanticSource,
        ):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "semantic-sync-looker",
                    "method": "semantic.syncSource",
                    "params": {
                        "sourceKind": "looker",
                        "endpoint": "https://looker.example/api",
                        "dryRun": False,
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        sync = frame["payload"]["sync"]
        assert sync["source_name"] == "looker"
        assert sync["applied_metric_ids"] == ["looker:monthly_active_users"]
        assert sync["applied_glossary_term_ids"] == ["term.monthly_active_users"]
        assert sync["applied_verified_query_ids"] == ["looker:look-123"]

    async def test_semantic_sync_source_unity_catalog_accepts_hyphenated_kind(
        self,
        rpc_handler,
        mock_ws,
        app_state,
    ):
        with patch(
            "ds_agent.memory.semantic.infrastructure.adapters.UnityCatalogAdapter",
            _FakeUnityCatalogSemanticSource,
        ):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "semantic-sync-unity",
                    "method": "semantic.syncSource",
                    "params": {
                        "sourceKind": "unity-catalog",
                        "endpoint": "https://unity.example/catalog",
                        "dryRun": False,
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        sync = frame["payload"]["sync"]
        assert sync["source_name"] == "unity_catalog"
        assert sync["applied_table_ids"] == ["main.analytics.orders"]
        assert sync["trust_diffs"][0]["status"] == "add"

    async def test_run_scorecard(self, rpc_handler, mock_ws, app_state):
        with patch.object(
            app_state,
            "get_run_scorecard",
            return_value={"runId": "run-123", "weightedScore": 0.82},
        ) as get_run_scorecard:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "run-scorecard",
                    "method": "run.scorecard",
                    "params": {"runId": "run-123"},
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["scorecard"]["runId"] == "run-123"
        assert frame["payload"]["scorecard"]["weightedScore"] == 0.82
        get_run_scorecard.assert_called_once_with("run-123")

    async def test_run_submit_human_rubric(self, rpc_handler, mock_ws, app_state):
        with patch.object(
            app_state,
            "submit_run_human_rubric",
            return_value={"runId": "run-123", "weightedScore": 0.91},
        ) as submit_run_human_rubric:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "run-submit-human",
                    "method": "run.submitHumanRubric",
                    "params": {
                        "runId": "run-123",
                        "reviewerId": "reviewer-1",
                        "dimensions": {"scoping_accuracy": 0.4},
                        "comment": "Scope framing needs work.",
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["scorecard"]["runId"] == "run-123"
        assert frame["payload"]["scorecard"]["weightedScore"] == 0.91
        submit_run_human_rubric.assert_called_once_with(
            "run-123",
            "reviewer-1",
            {"scoping_accuracy": 0.4},
            "Scope framing needs work.",
        )

    async def test_run_shadow_compare(self, rpc_handler, mock_ws, app_state):
        with patch.object(
            app_state,
            "run_shadow_compare",
            return_value={"runId": "run-123", "weightedScore": 0.88},
        ) as run_shadow_compare:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "run-shadow-compare",
                    "method": "run.shadowCompare",
                    "params": {
                        "runId": "run-123",
                        "model": "openai/gpt-4.1-mini",
                        "shadowFactor": 0.5,
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["scorecard"]["runId"] == "run-123"
        assert frame["payload"]["scorecard"]["weightedScore"] == 0.88
        run_shadow_compare.assert_called_once_with(
            "run-123",
            "openai/gpt-4.1-mini",
            0.5,
        )

    async def test_eval_regression_board(self, rpc_handler, mock_ws, app_state):
        with patch.object(
            app_state,
            "get_regression_board",
            return_value={"totalRecords": 6, "alerts": []},
        ) as get_regression_board:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "eval-regression-board",
                    "method": "eval.regressionBoard",
                    "params": {
                        "mode": "online",
                        "domain": "retail",
                        "recentWindow": 5,
                        "baselineWindowDays": 10,
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["board"]["totalRecords"] == 6
        get_regression_board.assert_called_once_with("online", "retail", 5, 10)

    async def test_eval_freeze_regression_baseline(self, rpc_handler, mock_ws, app_state):
        with patch.object(
            app_state,
            "freeze_regression_baseline",
            return_value={
                "baseline": {"baselineId": "baseline-123", "commitSha": "abc123"},
                "board": {"totalRecords": 6, "baselineSource": "frozen"},
            },
        ) as freeze_regression_baseline:
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "eval-freeze-baseline",
                    "method": "eval.freezeRegressionBaseline",
                    "params": {
                        "commitSha": "abc123",
                        "mode": "online",
                        "domain": "retail",
                        "recentWindow": 5,
                        "baselineWindowDays": 10,
                        "windowDays": 21,
                    },
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["baseline"]["baselineId"] == "baseline-123"
        assert frame["payload"]["board"]["baselineSource"] == "frozen"
        freeze_regression_baseline.assert_called_once_with(
            "abc123",
            "online",
            "retail",
            5,
            10,
            21,
        )

    def test_submit_run_human_rubric_triggers_regression_alert_dispatch(self, app_state):
        runtime_run = MagicMock(session_id="session-1", run_id="run-123", task_id="task-1")
        task = MagicMock(domain="retail")
        run = MagicMock()

        with (
            patch.object(
                app_state,
                "_load_eval_task_and_run_for_runtime_run",
                return_value=(runtime_run, MagicMock(), task, run),
            ),
            patch(
                "ds_agent.evaluation.application.use_cases.ingest_human_rubric.IngestHumanRubric"
            ) as ingest_human_rubric,
            patch.object(
                app_state,
                "_maybe_dispatch_regression_alerts_for_task",
            ) as maybe_dispatch,
            patch.object(
                app_state,
                "_build_run_scorecard",
                return_value={"runId": "run-123", "weightedScore": 0.91},
            ),
        ):
            ingest_human_rubric.return_value.execute.return_value = None

            payload = app_state.submit_run_human_rubric(
                "run-123",
                "reviewer-1",
                {"scoping_accuracy": 0.4},
                "Scope framing needs work.",
            )

        assert payload["runId"] == "run-123"
        maybe_dispatch.assert_called_once_with(
            runtime_run=runtime_run,
            domain="retail",
            dispatch_source="runtime",
        )

    def test_run_shadow_compare_triggers_regression_alert_dispatch(self, app_state):
        runtime_run = MagicMock(session_id="session-1", run_id="run-123", task_id="task-1")
        task = MagicMock(domain="retail")
        run = MagicMock()

        with (
            patch.object(
                app_state,
                "_load_eval_task_and_run_for_runtime_run",
                return_value=(runtime_run, MagicMock(), task, run),
            ),
            patch(
                "ds_agent.evaluation.infrastructure.orchestrator.agent_eval_orchestrator.AgentEvalOrchestrator"
            ),
            patch(
                "ds_agent.evaluation.application.use_cases.run_shadow_comparison.RunShadowComparison"
            ) as run_shadow_comparison,
            patch.object(
                app_state,
                "_maybe_dispatch_regression_alerts_for_task",
            ) as maybe_dispatch,
            patch.object(
                app_state,
                "_build_run_scorecard",
                return_value={"runId": "run-123", "weightedScore": 0.88},
            ),
        ):
            run_shadow_comparison.return_value.execute.return_value = None

            payload = app_state.run_shadow_compare(
                "run-123",
                "openai/gpt-4.1-mini",
                0.5,
            )

        assert payload["runId"] == "run-123"
        maybe_dispatch.assert_called_once_with(
            runtime_run=runtime_run,
            domain="retail",
            dispatch_source="runtime",
        )

    async def test_policy_get(self, rpc_handler, mock_ws, app_state):
        app_state.upsert_recurring_goal(
            session_id="session-1",
            prompt="Check weekly metrics",
            interval_seconds=600,
        )
        app_state.set_standing_orders(["Do not auto-delete artifacts"])
        app_state.set_action_matrix_overrides({"jira_create": {"delegate": "auto"}})

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "policy-get",
                "method": "policy.get",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["automationProfile"] == "balanced"
        assert len(frame["payload"]["recurringGoals"]) == 1
        assert frame["payload"]["standingOrders"] == ["Do not auto-delete artifacts"]
        assert frame["payload"]["actionMatrixOverrides"] == {"jira_create": {"delegate": "auto"}}
        assert frame["payload"]["actionMatrixOverrideCount"] == 1
        jira_row = next(
            row
            for row in frame["payload"]["actionMatrixRows"]
            if row["actionClass"] == "jira_create"
        )
        assert jira_row["defaultVerdicts"]["delegate"] == "ask"
        assert jira_row["effectiveVerdicts"]["delegate"] == "auto"
        assert jira_row["overrideVerdicts"] == {"delegate": "auto"}

    async def test_policy_upsert_recurring_goal(self, rpc_handler, mock_ws, app_state):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "policy-upsert",
                "method": "policy.upsertRecurringGoal",
                "params": {
                    "sessionId": "session-7",
                    "prompt": "Review failed runs",
                    "intervalSeconds": 300,
                    "enabled": True,
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["goal"]["sessionId"] == "session-7"
        assert app_state.get_status()["recurringGoalCount"] == 1

    async def test_policy_set_action_matrix_overrides(self, rpc_handler, mock_ws, app_state):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "policy-matrix",
                "method": "policy.setActionMatrixOverrides",
                "params": {
                    "overrides": {
                        "jira_create": {"delegate": "auto"},
                        "prod_deploy": {"supervised": "approve"},
                    }
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["actionMatrixOverrideCount"] == 2
        assert frame["payload"]["actionMatrixOverrides"] == {
            "jira_create": {"delegate": "auto"},
            "prod_deploy": {"supervised": "approve"},
        }
        assert app_state.build_action_matrix().lookup("jira_create", "delegate").value == "auto"
        assert (
            app_state.build_action_matrix().lookup("prod_deploy", "supervised").value == "approve"
        )

    async def test_decision_os_overview(self, rpc_handler, mock_ws, app_state):
        _seed_decision_os_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-overview",
                "method": "decisionOs.overview",
                "params": {"runLimit": 10, "modelLimit": 10, "decisionLimit": 10},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["summary"]["runCount"] == 2
        assert frame["payload"]["summary"]["modelCount"] == 2
        assert frame["payload"]["summary"]["monitorStateCount"] == 1
        assert frame["payload"]["runs"][0]["run_id"] == "run-candidate"
        assert frame["payload"]["runs"][0]["review_artifacts"][0]["skill_name"] == (
            "retrain-vs-rollback"
        )
        assert frame["payload"]["models"][0]["model_id"] == "m_churn_candidate"
        assert frame["payload"]["monitorStates"][0]["model_id"] == "m_churn_lightgbm"

    async def test_decision_os_compare_runs(self, rpc_handler, mock_ws, app_state):
        _seed_decision_os_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-compare",
                "method": "decisionOs.compareRuns",
                "params": {"runAId": "run-champion", "runBId": "run-candidate"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["run_a_id"] == "run-champion"
        assert frame["payload"]["run_b_id"] == "run-candidate"
        assert frame["payload"]["feature_set"]["version_changed"] == [["f_user_activity_30d", 1, 2]]

    async def test_decision_os_request_promotion(self, rpc_handler, mock_ws, app_state):
        seeded = _seed_decision_os_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-promotion",
                "method": "decisionOs.requestPromotion",
                "params": {
                    "candidateRunId": "run-candidate",
                    "targetStage": "staging",
                    "approvers": ["growth-ds", "ml-lead", "mlops-oncall"],
                    "rollbackPlanRef": seeded["rollback_plan_ref"],
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["candidate_run_id"] == "run-candidate"
        assert frame["payload"]["target_stage"] == "staging"
        assert frame["payload"]["chain_state"] == "pending_DS"
        events = app_state.list_runtime_events(limit=5, category="deployment")
        assert any(event.kind == "decision_os.promotion_requested" for event in events)

    async def test_decision_os_resolve_promotion(self, rpc_handler, mock_ws, app_state):
        seeded = _seed_decision_os_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-promotion",
                "method": "decisionOs.requestPromotion",
                "params": {
                    "candidateRunId": "run-candidate",
                    "targetStage": "production",
                    "approvers": ["growth-ds", "ml-lead", "mlops-oncall"],
                    "rollbackPlanRef": seeded["rollback_plan_ref"],
                },
            }
        )

        decision_id = mock_ws.sent[0]["payload"]["decision_id"]
        mock_ws.sent.clear()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-resolve",
                "method": "decisionOs.resolvePromotion",
                "params": {
                    "decisionId": decision_id,
                    "decision": "approved",
                    "approver": "growth-ds",
                    "note": "DS approved",
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["decision_id"] == decision_id
        assert frame["payload"]["chain_state"] == "pending_Lead"
        events = app_state.list_runtime_events(limit=10, category="deployment")
        assert any(event.kind == "decision_os.promotion_resolved" for event in events)

    async def test_decision_os_review_flow_e2e(self, rpc_handler, mock_ws, app_state):
        seeded = _seed_decision_os_state(app_state)
        workspace = Path(seeded["workspace_dir"])

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-compare",
                "method": "decisionOs.compareRuns",
                "params": {"runAId": "run-champion", "runBId": "run-candidate"},
            }
        )
        assert mock_ws.sent[0]["ok"] is True
        assert mock_ws.sent[0]["payload"]["run_b_id"] == "run-candidate"
        mock_ws.sent.clear()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-promotion",
                "method": "decisionOs.requestPromotion",
                "params": {
                    "candidateRunId": "run-candidate",
                    "targetStage": "production",
                    "approvers": ["growth-ds", "ml-lead", "mlops-oncall"],
                    "rollbackPlanRef": seeded["rollback_plan_ref"],
                },
            }
        )
        decision_id = mock_ws.sent[0]["payload"]["decision_id"]
        mock_ws.sent.clear()

        for approver in ("growth-ds", "ml-lead", "mlops-oncall"):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": f"decision-os-resolve-{approver}",
                    "method": "decisionOs.resolvePromotion",
                    "params": {
                        "decisionId": decision_id,
                        "decision": "approved",
                        "approver": approver,
                        "note": f"{approver} approved",
                    },
                }
            )
            assert mock_ws.sent[0]["ok"] is True
            mock_ws.sent.clear()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-apply",
                "method": "decisionOs.applyPromotion",
                "params": {"decisionId": decision_id},
            }
        )
        apply_frame = mock_ws.sent[0]
        assert apply_frame["ok"] is True
        assert apply_frame["payload"]["applied_alias"] == "champion"
        assert apply_frame["payload"]["candidate_model_id"] == seeded["candidate_model_id"]
        mock_ws.sent.clear()

        monitoring_dir = workspace / "data" / "monitoring" / "post_deploy"
        monitoring_dir.mkdir(parents=True, exist_ok=True)
        reference_path = workspace / "reference_candidate.csv"
        current_path = workspace / "current_candidate.csv"
        reference_path.write_text("f_user_activity_30d\n1\n1\n1\n1\n1\n", encoding="utf-8")
        current_path.write_text("f_user_activity_30d\n10\n10\n10\n10\n10\n", encoding="utf-8")
        snapshot_path = monitoring_dir / (
            f"{seeded['candidate_model_id']}-v{seeded['candidate_model_version']}.json"
        )
        snapshot_path.write_text(
            json.dumps(
                {
                    "reference_path": str(reference_path),
                    "current_path": str(current_path),
                    "current_metrics": {"f1_macro": 0.68, "fp_rate": 0.19},
                    "latency_p95_ms": 155.0,
                    "qps": 28.0,
                    "observed_at": datetime(2026, 4, 16, 14, tzinfo=UTC).isoformat(),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        container = app_state._get_decision_os_container()
        states = container.post_deploy_monitor.periodic_sweep(window="7d")
        assert len(states) == 1
        assert states[0].model_id == seeded["candidate_model_id"]
        assert states[0].overall_status == "alert"

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-status",
                "method": "decisionOs.getPostDeployStatus",
                "params": {"modelId": seeded["candidate_model_id"], "window": "7d"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["model_id"] == seeded["candidate_model_id"]
        assert frame["payload"]["summary"]["overall_status"] == "alert"
        assert frame["payload"]["alerts"]

        events = app_state.list_runtime_events(limit=20, category="deployment")
        event_kinds = {event.kind for event in events}
        assert "decision_os.promotion_requested" in event_kinds
        assert "decision_os.promotion_resolved" in event_kinds
        assert "decision_os.promotion_applied" in event_kinds
        assert "post_deploy_alert" in event_kinds

    async def test_decision_os_get_post_deploy_status(self, rpc_handler, mock_ws, app_state):
        _seed_decision_os_state(app_state)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "decision-os-status",
                "method": "decisionOs.getPostDeployStatus",
                "params": {"modelId": "m_churn_lightgbm", "window": "7d"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["model_id"] == "m_churn_lightgbm"
        assert frame["payload"]["summary"]["overall_status"] == "alert"
        assert frame["payload"]["alerts"] == ["Drift threshold exceeded"]

    async def test_runtime_events_list(self, rpc_handler, mock_ws, app_state):
        app_state.record_runtime_event(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="info",
            message="Recovered session can resume.",
            session_id="session-11",
            surface="daemon",
            source="startup_recovery",
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "runtime-events",
                "method": "runtime.events.list",
                "params": {"limit": 10, "sessionId": "session-11"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert len(frame["payload"]["events"]) == 1
        event = frame["payload"]["events"][0]
        assert event["category"] == "recovery"
        assert event["kind"] == "recovery.resume_recommended"
        assert event["sessionId"] == "session-11"

    async def test_status_get(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "s1",
                "method": "status.get",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert "model" in frame["payload"]
        assert "qualityPreset" in frame["payload"]
        assert "mode" in frame["payload"]
        assert "pendingApprovals" in frame["payload"]
        assert "autonomousRuntimeEnabled" in frame["payload"]
        assert "autonomousRuntimeRunning" in frame["payload"]
        assert "sensorBacklog" in frame["payload"]
        assert "recoveredSessions" in frame["payload"]
        assert "automationProfile" in frame["payload"]
        assert "recurringGoalCount" in frame["payload"]
        assert "standingOrderCount" in frame["payload"]
        assert "resourcePressure" in frame["payload"]
        assert "authorityOverlay" in frame["payload"]
        assert "authorityOverlayStartedAt" in frame["payload"]
        assert "authorityOverlayExpiresAt" in frame["payload"]
        assert "effectiveAuthorityMode" in frame["payload"]

    async def test_usage_summary_rpc(self, rpc_handler, mock_ws, app_state):
        app_state.config.provider.budget_warning_threshold_pct = 90.0
        app_state.organization_store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
            cost_usd=2.5,
            session_id="session-1",
            cache_savings_usd=0.25,
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "usage-1",
                "method": "usage.summary",
                "params": {"sessionId": "session-1"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["monthlyCostUsd"] == 2.5
        assert frame["payload"]["sessionCostUsd"] == 2.5
        assert frame["payload"]["cacheSavingsUsd"] == 0.25
        assert frame["payload"]["warningThresholdPct"] == 90.0

    async def test_chat_send_blocks_when_monthly_budget_exceeded(
        self,
        rpc_handler,
        mock_ws,
        app_state,
    ):
        app_state.config.provider.max_budget_usd = 1.0
        app_state.organization_store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            cost_usd=1.0,
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "budget-limit",
                "method": "chat.send",
                "params": {"message": "Analyze data"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert frame["error"]["code"] == "INVALID_PARAMS"
        assert "monthly budget exceeded" in frame["error"]["message"].lower()

    async def test_files_list_empty(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "f1",
                "method": "files.list",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["files"] == []

    async def test_files_upload(self, rpc_handler, mock_ws, tmp_path):
        import base64

        content = b"col1,col2\n1,2\n3,4"
        b64 = base64.b64encode(content).decode()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "f2",
                "method": "files.upload",
                "params": {"name": "test.csv", "data": b64},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert "path" in frame["payload"]

    async def test_provider_list(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "p1",
                "method": "provider.list",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        providers = frame["payload"]["providers"]
        assert len(providers) >= 6
        names = [p["id"] for p in providers]
        assert "anthropic" in names
        assert "ollama" in names

    async def test_project_create_and_list(self, rpc_handler, mock_ws):
        # Create
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pc1",
                "method": "project.create",
                "params": {"name": "Test Project"},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        project_id = frame["payload"]["projectId"]
        assert project_id

        # List
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pl1",
                "method": "project.list",
            }
        )
        frame2 = mock_ws.sent[1]
        assert frame2["ok"] is True
        assert len(frame2["payload"]["projects"]) == 1

    async def test_files_list_project_reads_project_artifacts(
        self, rpc_handler, mock_ws, app_state
    ):
        project_id = app_state.create_project("Test Project")
        project_artifact = (
            app_state._workspace._get_project_store().get_project_dir(project_id)
            / "artifacts"
            / "report.md"
        )
        project_artifact.write_text("# Report", encoding="utf-8")

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pf1",
                "method": "files.list",
                "params": {"projectId": project_id},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        paths = {f["path"] for f in frame["payload"]["files"]}
        assert "artifacts/report.md" in paths

    async def test_chat_send_creates_task(self, rpc_handler, mock_ws, app_state):
        """chat.send should return sessionId/runId and start agent in background."""
        # Mock agent creation to avoid needing real LLM provider
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis done.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.01

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "c1",
                    "method": "chat.send",
                    "params": {"message": "Analyze the data"},
                }
            )

        # Should get immediate response with sessionId
        res_frame = mock_ws.sent[0]
        assert res_frame["type"] == "res"
        assert res_frame["ok"] is True
        assert "sessionId" in res_frame["payload"]
        assert "runId" in res_frame["payload"]
        assert res_frame["payload"]["status"] == "running"

        # Wait for background task
        await asyncio.sleep(0.1)

        # Should receive stream.done event
        events = [f for f in mock_ws.sent if f.get("type") == "event"]
        done_events = [e for e in events if e.get("event") == "stream.done"]
        assert len(done_events) == 1
        assert done_events[0]["payload"]["content"] == "Analysis done."
        run = app_state.get_run(res_frame["payload"]["runId"])
        assert run is not None
        assert run.status.value == "succeeded"

    async def test_chat_send_redacts_background_exception(self, rpc_handler, mock_ws, app_state):
        """Background agent failures should not leak raw exception details to clients."""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("secret backend failure"))
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "c2",
                    "method": "chat.send",
                    "params": {"message": "Analyze the data"},
                }
            )

        await asyncio.sleep(0.1)

        events = [f for f in mock_ws.sent if f.get("type") == "event"]
        done_events = [e for e in events if e.get("event") == "stream.done"]
        assert len(done_events) == 1
        assert done_events[0]["payload"]["content"] == "Internal server error"

    async def test_chat_abort(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "a1",
                "method": "chat.abort",
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        # No running task, so reason = no_running_task
        assert frame["payload"].get("reason") == "no_running_task"

    async def test_run_wait_returns_terminal_state(self, rpc_handler, mock_ws, app_state):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="Analysis done.")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.01

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "r1",
                    "method": "run.start",
                    "params": {"message": "Analyze the data", "sessionId": "run-session"},
                }
            )

        start_frame = mock_ws.sent[0]
        run_id = start_frame["payload"]["runId"]
        await asyncio.sleep(0.05)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "r2",
                "method": "run.wait",
                "params": {"runId": run_id, "timeoutMs": 1000},
            }
        )

        wait_frame = mock_ws.sent[-1]
        assert wait_frame["ok"] is True
        assert wait_frame["payload"]["runId"] == run_id
        assert wait_frame["payload"]["status"] == "succeeded"

    async def test_run_list_filters_by_session(self, rpc_handler, mock_ws, app_state):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="done")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "rl1",
                    "method": "run.start",
                    "params": {"message": "hello", "sessionId": "session-a"},
                }
            )

        await asyncio.sleep(0.05)
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "rl2",
                "method": "run.list",
                "params": {"sessionId": "session-a"},
            }
        )

        list_frame = mock_ws.sent[-1]
        assert list_frame["ok"] is True
        assert len(list_frame["payload"]["runs"]) == 1
        assert list_frame["payload"]["runs"][0]["sessionId"] == "session-a"

    async def test_session_list_returns_runtime_sessions(self, rpc_handler, mock_ws, app_state):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="done")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "sl1",
                    "method": "run.start",
                    "params": {"message": "hello", "sessionId": "session-runtime"},
                }
            )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "sl2",
                "method": "session.list",
                "params": {"limit": 10},
            }
        )

        frame = mock_ws.sent[-1]
        assert frame["ok"] is True
        assert len(frame["payload"]["sessions"]) == 1
        assert frame["payload"]["sessions"][0]["sessionId"] == "session-runtime"

    async def test_runtime_payloads_include_telegram_thread_context(
        self,
        rpc_handler,
        mock_ws,
        app_state,
    ):
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value="done")
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "ctx1",
                    "method": "run.start",
                    "params": {"message": "hello", "sessionId": "telegram:ops-room:77"},
                }
            )

        await asyncio.sleep(0.05)
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ctx2",
                "method": "run.list",
                "params": {"sessionId": "telegram:ops-room:77"},
            }
        )
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ctx3",
                "method": "session.list",
                "params": {"limit": 10},
            }
        )

        runs_frame = mock_ws.sent[-2]
        sessions_frame = mock_ws.sent[-1]
        run = runs_frame["payload"]["runs"][0]
        session = sessions_frame["payload"]["sessions"][0]

        assert run["sessionId"] == "telegram:ops-room:77"
        assert run["conversationId"] == "ops-room"
        assert run["threadId"] == "77"
        assert run["threadLabel"] == "topic 77"
        assert run["sessionLabel"] == "chat ops-room / topic 77"
        assert session["sessionId"] == "telegram:ops-room:77"
        assert session["conversationId"] == "ops-room"
        assert session["threadId"] == "77"
        assert session["threadLabel"] == "topic 77"
        assert session["sessionLabel"] == "chat ops-room / topic 77"

    async def test_task_list_returns_tracked_tasks(self, rpc_handler, mock_ws, app_state):
        started = asyncio.Event()

        async def _slow_run(_message: str) -> str:
            started.set()
            await asyncio.sleep(0.2)
            return "done"

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=_slow_run)
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "tl1",
                    "method": "run.start",
                    "params": {"message": "long", "sessionId": "task-session"},
                }
            )

        await started.wait()
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "tl2",
                "method": "task.list",
                "params": {"limit": 10},
            }
        )

        frame = mock_ws.sent[-1]
        assert frame["ok"] is True
        assert len(frame["payload"]["tasks"]) == 1
        assert frame["payload"]["tasks"][0]["status"] == "running"

    async def test_run_abort_cancels_running_task(self, rpc_handler, mock_ws, app_state):
        started = asyncio.Event()

        async def _slow_run(message: str) -> str:
            started.set()
            await asyncio.sleep(10)
            return message

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=_slow_run)
        mock_agent._budget = MagicMock()
        mock_agent._budget.state = MagicMock()
        mock_agent._budget.state.total_cost_usd = 0.0

        with patch.object(app_state._sessions, "_create_agent", return_value=mock_agent):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "ra1",
                    "method": "run.start",
                    "params": {"message": "long job", "sessionId": "abort-session"},
                }
            )

        run_id = mock_ws.sent[0]["payload"]["runId"]
        await started.wait()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ra2",
                "method": "run.abort",
                "params": {"runId": run_id},
            }
        )
        await asyncio.sleep(0.05)

        abort_frame = mock_ws.sent[-1]
        assert abort_frame["ok"] is True
        assert abort_frame["payload"]["runId"] == run_id
        assert abort_frame["payload"]["status"] == "cancelled"

    async def test_approval_list(self, rpc_handler, mock_ws, app_state):
        app_state.approval_store.create(
            session_id="session-1",
            run_id="run-1",
            surface="ws",
            question="Approve training?",
            options=["yes", "no"],
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ap1",
                "method": "approval.list",
                "params": {"sessionId": "session-1"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert len(frame["payload"]["approvals"]) == 1
        assert frame["payload"]["approvals"][0]["status"] == "pending"

    async def test_approval_resolve(self, rpc_handler, mock_ws, app_state):
        approval = app_state.approval_store.create(
            session_id="session-1",
            run_id="run-1",
            surface="ws",
            question="Approve training?",
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ap2",
                "method": "approval.resolve",
                "params": {
                    "approvalId": approval.approval_id,
                    "decision": "approved",
                    "response": "yes",
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["status"] == "approved"
        resolved = app_state.approval_store.get(approval.approval_id)
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.response == "yes"

    async def test_chat_history_empty(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "h1",
                "method": "chat.history",
                "params": {"sessionId": "nonexistent"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["messages"] == []

    async def test_chat_history_reads_transcript_store(self, rpc_handler, mock_ws, app_state):
        from ds_agent.domain.entities.messages import ChatMessage, Role

        app_state.transcript_store.replace_messages(
            "session-1",
            [
                ChatMessage(role=Role.USER, content="Hello"),
                ChatMessage(role=Role.ASSISTANT, content="Hi"),
            ],
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "h2",
                "method": "chat.history",
                "params": {"sessionId": "session-1"},
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert len(frame["payload"]["messages"]) == 2


# ---------------------------------------------------------------------------
# AppState
# ---------------------------------------------------------------------------


class TestAppState:
    """Test shared application state management."""

    def test_get_status(self, app_state):
        status = app_state.get_status()
        assert "model" in status
        assert "qualityPreset" in status
        assert "mode" in status
        assert status["activeSessions"] == 0
        assert "autonomousRuntimeEnabled" in status
        assert "autonomousRuntimeRunning" in status
        assert "recoveredSessions" in status

    def test_list_files_empty(self, app_state):
        files = app_state.list_files()
        assert files == []

    def test_list_files_with_content(self, app_state, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir(exist_ok=True)
        (workspace / "data.csv").write_text("a,b\n1,2")
        (workspace / "plot.png").write_bytes(b"\x89PNG")

        files = app_state.list_files()
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert "data.csv" in names
        assert "plot.png" in names

    def test_record_runtime_event_notifies_listener(self, app_state):
        seen: list[tuple[str, dict]] = []

        def _listener(event: str, payload: dict) -> None:
            seen.append((event, payload))

        app_state.register_runtime_listener(_listener)
        try:
            app_state.record_runtime_event(
                category="pressure",
                kind="system.resource.pressure",
                severity="warning",
                message="Runtime pressure changed.",
                session_id="autonomous:system",
                surface="daemon",
                source="system_resource",
            )
        finally:
            app_state.unregister_runtime_listener(_listener)

        assert len(seen) == 1
        assert seen[0][0] == "runtime.alert"
        assert seen[0][1]["kind"] == "system.resource.pressure"

    def test_maybe_dispatch_regression_alerts_calls_dispatch_helper(self, app_state):
        runtime_run = MagicMock(session_id="session-1", run_id="run-1", surface="ws")

        with patch.object(app_state, "dispatch_regression_alerts") as dispatch_regression_alerts:
            app_state._maybe_dispatch_regression_alerts_for_task(
                runtime_run=runtime_run,
                domain="retail",
                dispatch_source="runtime",
            )

        dispatch_regression_alerts.assert_called_once_with(
            mode=None,
            domain="retail",
            skip_if_unchanged=True,
            dispatch_source="runtime",
            session_id="session-1",
            run_id="run-1",
            surface="ws",
        )

    def test_maybe_dispatch_regression_alerts_records_failure_event(self, app_state):
        runtime_run = MagicMock(session_id="session-2", run_id="run-2", surface="daemon")

        with patch.object(
            app_state,
            "dispatch_regression_alerts",
            side_effect=RuntimeError("webhook failed"),
        ):
            app_state._maybe_dispatch_regression_alerts_for_task(
                runtime_run=runtime_run,
                domain="retail",
                dispatch_source="schedule",
            )

        events = app_state.list_runtime_events(limit=10, category="evaluation")
        assert any(getattr(event, "kind", "") == "regression_alert.failed" for event in events)


# ---------------------------------------------------------------------------
# FastAPI app — HTTP routes
# ---------------------------------------------------------------------------


class TestHTTPRoutes:
    """Test HTTP endpoints using HTTPX TestClient."""

    @pytest.fixture()
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        from ds_agent.api.app import create_app
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig

        app = create_app()
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
        )
        app.state.app_state = AppState(config=config)
        return TestClient(app)

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_get_status(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "model" in data
        assert "qualityPreset" in data
        assert "mode" in data

    def test_get_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "provider" in data["config"]

    def test_set_config(self, client):
        resp = client.post(
            "/api/config",
            json={"path": "agent.mode", "value": "step-by-step"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Verify
        resp2 = client.get("/api/config")
        assert resp2.json()["config"]["agent"]["mode"] == "step-by-step"

    def test_set_config_updates_backend_observability(self, client):
        with patch("ds_agent.api.ws_handler.configure_backend_observability") as configure:
            resp = client.post(
                "/api/config",
                json={"path": "observability.error_reporting_enabled", "value": True},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        configure.assert_called_once_with(client.app.state.app_state.config)

    def test_list_files_empty(self, client):
        resp = client.get("/api/files")
        assert resp.status_code == 200
        assert resp.json()["files"] == []

    def test_plot_not_found(self, client):
        resp = client.get("/api/plots/nonexistent.png")
        assert resp.status_code == 404

    def test_plot_path_traversal_blocked(self, client, tmp_path):
        # Create a file outside workspace
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")

        resp = client.get("/api/plots/../../secret.txt")
        assert resp.status_code in (403, 404)

    def test_admin_audit_export(self, client, tmp_path):
        from ds_agent.runtime.transcript_store import get_runtime_storage_root

        audit_path = (
            get_runtime_storage_root(client.app.state.app_state.config.agent.workspace_dir)
            / "audit_log.jsonl"
        )
        audit_path.write_text(
            '{"event":"post_tool_use","tool":"generate_report","timestamp":1713052800.0}\n',
            encoding="utf-8",
        )

        resp = client.get(
            "/admin/audit-log/export",
            params={
                "startDate": "2024-04-13",
                "endDate": "2024-04-15",
                "format": "csv",
            },
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=" in resp.headers["content-disposition"]
        assert "generate_report" in resp.text

    def test_admin_audit_export_requires_admin(self, client):
        from ds_agent.domain.entities.organization import OrgRole

        client.app.state.app_state.organization_store.invite_member(
            "viewer-1",
            role=OrgRole.VIEWER,
        )

        resp = client.get(
            "/admin/audit-log/export",
            params={
                "startDate": "2024-04-13",
                "endDate": "2024-04-15",
                "actorId": "viewer-1",
            },
        )

        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    def test_support_bundle_export(self, client, tmp_path):
        from ds_agent.runtime.transcript_store import get_runtime_storage_root

        runtime_root = get_runtime_storage_root(
            client.app.state.app_state.config.agent.workspace_dir
        )
        runtime_root.mkdir(parents=True, exist_ok=True)
        (runtime_root / "audit_log.jsonl").write_text(
            json.dumps(
                {
                    "event": "post_tool_use",
                    "tool": "generate_report",
                    "token": "top-secret-token",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        output_path = tmp_path / "exports" / "bundle.zip"
        resp = client.post("/api/support/bundle", json={"outputPath": str(output_path)})

        assert resp.status_code == 200
        exported = Path(resp.json()["path"])
        assert exported.exists()

        with zipfile.ZipFile(exported) as archive:
            names = set(archive.namelist())
            assert "manifest.json" in names
            assert "config.yaml" in names
            assert "logs/audit_log.jsonl" in names
            audit_log = archive.read("logs/audit_log.jsonl").decode("utf-8")
            assert "top-secret-token" not in audit_log
            assert "***REDACTED***" in audit_log

    def test_support_bundle_export_requires_output_path(self, client):
        resp = client.post("/api/support/bundle", json={"outputPath": "   "})

        assert resp.status_code == 400
        assert "outputPath" in resp.json()["detail"]

    def test_usage_summary_http_route(self, client):
        client.app.state.app_state.config.provider.budget_warning_threshold_pct = 90.0
        client.app.state.app_state.organization_store.record_usage(
            actor_id="local-user",
            provider="anthropic",
            model="anthropic/claude-sonnet-4-6",
            cost_usd=3.0,
            session_id="session-usage",
            cache_savings_usd=0.5,
        )

        resp = client.get("/api/usage/summary", params={"sessionId": "session-usage"})

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["monthlyCostUsd"] == 3.0
        assert payload["sessionCostUsd"] == 3.0
        assert payload["cacheSavingsUsd"] == 0.5
        assert payload["warningThresholdPct"] == 90.0


# ---------------------------------------------------------------------------
# Phase 3: Security / Error / RPC gap-filling tests
# ---------------------------------------------------------------------------


class TestConfigSetSecurity:
    """SEC-01: Config path whitelist validation."""

    async def test_disallowed_path_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "sec1",
                "method": "config.set",
                "params": {"path": "provider.api_keys", "value": "hacked"},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "[DSA-SYS-002]" in frame["error"]["message"]
        assert "not allowed" in frame["error"]["message"].lower()

    async def test_empty_path_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "sec2",
                "method": "config.set",
                "params": {"path": "", "value": "x"},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False


class TestFileUploadSecurity:
    """SEC-03: Upload validation — path traversal, extension, size."""

    async def test_path_traversal_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "u1",
                "method": "files.upload",
                "params": {"name": "../../../etc/passwd", "data": "dGVzdA=="},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        msg = frame["error"]["message"].lower()
        assert "path" in msg or "separator" in msg

    async def test_disallowed_extension_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "u2",
                "method": "files.upload",
                "params": {"name": "malware.exe", "data": "dGVzdA=="},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "not allowed" in frame["error"]["message"].lower()

    async def test_empty_name_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "u3",
                "method": "files.upload",
                "params": {"name": "", "data": "dGVzdA=="},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False

    async def test_invalid_base64_rejected(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "u4",
                "method": "files.upload",
                "params": {"name": "test.csv", "data": "!!!!"},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "base64" in frame["error"]["message"].lower()


class TestProviderRpcMethods:
    """Provider model catalog and auth status RPCs."""

    async def test_provider_models_returns_catalog(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pm1",
                "method": "provider.models",
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        models = frame["payload"]["models"]
        assert len(models) >= 10
        # Check structure
        m = models[0]
        assert "id" in m
        assert "provider" in m
        assert "displayName" in m

    async def test_provider_auth_status(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pa1",
                "method": "provider.authStatus",
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        statuses = frame["payload"]["statuses"]
        assert "anthropic" in statuses
        assert "ollama" in statuses
        assert statuses["ollama"] == "local"

    async def test_provider_auth_status_uses_gemini_token_store(
        self, rpc_handler, mock_ws, app_state
    ):
        app_state.token_store.save(
            "google:default",
            AuthProfile(
                type="oauth",
                provider="gemini",
                oauth=OAuthTokenSet(
                    access="access",
                    refresh="refresh",
                    expires=9_999_999_999_999,
                    provider="gemini",
                ),
            ),
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "pa2",
                "method": "provider.authStatus",
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["statuses"]["gemini"] == "active"

    async def test_provider_health(self, rpc_handler, mock_ws):
        provider_snapshot = [
            {
                "id": "openai",
                "label": "OpenAI",
                "status": "ok",
                "hasCredentials": True,
                "authStatus": "active",
                "latencyMs": 180,
                "message": "Credentials are configured and ready.",
                "checkedAt": 1_713_052_800,
            }
        ]

        with patch(
            "ds_agent.runtime.provider_factory.get_provider_health_snapshot",
            new=AsyncMock(return_value=provider_snapshot),
        ):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "ph1",
                    "method": "provider.health",
                }
            )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["providers"] == provider_snapshot


class TestApiKeyManagement:
    """SEC-11: API key set/get with provider validation."""

    async def test_set_api_key_valid(self, rpc_handler, mock_ws):
        with patch("ds_agent.api.config_manager.save_config"):
            await rpc_handler.handle_message(
                {
                    "type": "req",
                    "id": "ak1",
                    "method": "config.setApiKey",
                    "params": {"provider": "anthropic", "key": "sk-ant-test123456"},
                }
            )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True

    async def test_set_api_key_unknown_provider(self, rpc_handler, mock_ws):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ak2",
                "method": "config.setApiKey",
                "params": {"provider": "unknown_provider", "key": "sk-test"},
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "unknown" in frame["error"]["message"].lower()

    async def test_get_api_keys_masked(self, rpc_handler, mock_ws, app_state):
        app_state.config_manager.set_api_key("anthropic", "sk-ant-very-long-key-12345")

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "gk1",
                "method": "config.getApiKeys",
            }
        )
        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        masked = frame["payload"]["keys"]["anthropic"]
        assert masked.startswith("sk-a")
        assert masked.endswith("2345")
        assert "..." in masked

    async def test_get_api_keys_short_masked(self, rpc_handler, mock_ws, app_state):
        app_state.config_manager.set_api_key("groq", "short")

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "gk2",
                "method": "config.getApiKeys",
            }
        )
        frame = mock_ws.sent[0]
        assert frame["payload"]["keys"]["groq"] == "***"


class _FakeConnectorAdapter:
    def execute_query(self, _spec):
        return [{"value": 1}]


class _FakeSemanticWarehouseAdapter:
    def get_schemas(self):
        from ds_agent.domain.interfaces.warehouse import SchemaInfo

        return [SchemaInfo(name="growth")]

    def get_tables(self, schema: str):
        from ds_agent.domain.interfaces.warehouse import TableInfo

        assert schema == "growth"
        return [TableInfo(name="subscription", schema=schema)]

    def get_columns(self, schema: str, table: str):
        from ds_agent.domain.interfaces.warehouse import ColumnInfo

        assert schema == "growth"
        assert table == "subscription"
        return [ColumnInfo(name="subscriber_id", data_type="uuid", nullable=False)]

    def execute_query(self, _spec):
        return [{"value": 1}]


class _FakeSnowflakeSemanticWarehouseAdapter:
    def get_schemas(self):
        from ds_agent.domain.interfaces.warehouse import SchemaInfo

        return [SchemaInfo(name="CURATED")]

    def get_tables(self, schema: str):
        from ds_agent.domain.interfaces.warehouse import TableInfo

        assert schema == "CURATED"
        return [TableInfo(name="ORDERS", schema=schema)]

    def get_columns(self, schema: str, table: str):
        from ds_agent.domain.interfaces.warehouse import ColumnInfo

        assert schema == "CURATED"
        assert table == "ORDERS"
        return [ColumnInfo(name="ORDER_ID", data_type="NUMBER", nullable=False)]

    def execute_query(self, _spec):
        return [{"value": 1}]


class _FakeLookerSemanticSource:
    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        source_name: str = "looker",
        owner: str = "looker",
    ) -> None:
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._owner = owner
        self.name = source_name

    def fetch_metrics(self, since):
        del since
        return [
            Metric.model_validate(
                {
                    "metric_id": "monthly_active_users",
                    "display_name": "Monthly Active Users",
                    "owner": self._owner,
                    "definition": "Looker MAU metric",
                    "synonyms": ["mau"],
                    "grain": "monthly",
                    "unit": "count",
                    "direction": "higher_is_better",
                    "calculation": {
                        "numerator": {
                            "source": "analytics.sessions",
                            "filter": "is_active = true",
                            "aggregation": "COUNT(DISTINCT user_id)",
                        }
                    },
                }
            )
        ]

    def fetch_glossary_terms(self, since):
        del since
        return [
            GlossaryTerm.model_validate(
                {
                    "term_id": "term.monthly_active_users",
                    "canonical_form": "monthly active users",
                    "definition": "Looker business term for MAU.",
                    "linked_metric_ids": ["monthly_active_users"],
                    "category": "metric",
                    "owner": self._owner,
                }
            )
        ]

    def fetch_tables(self, since):
        del since
        return []

    def fetch_verified_queries(self, since):
        del since
        return [
            VerifiedQuery.model_validate(
                {
                    "vq_id": "look-123",
                    "metric_id": "monthly_active_users",
                    "dialect": "bigquery",
                    "description": "Looker MAU explore SQL",
                    "sql_template": (
                        "SELECT COUNT(DISTINCT user_id) AS monthly_active_users "
                        "FROM analytics.sessions"
                    ),
                    "referenced_tables": ["analytics.sessions"],
                    "verified_by": self._owner,
                    "last_verified": "2026-04-16",
                    "verification_evidence": "https://looker.example/looks/123",
                }
            )
        ]


class _FakeUnityCatalogSemanticSource:
    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        source_name: str = "unity_catalog",
        owner: str = "unity_catalog",
    ) -> None:
        self.endpoint = endpoint
        self.auth_token = auth_token
        self._owner = owner
        self.name = source_name

    def fetch_metrics(self, since):
        del since
        return []

    def fetch_glossary_terms(self, since):
        del since
        return []

    def fetch_tables(self, since):
        del since
        return [
            TableTrust.model_validate(
                {
                    "fqtn": "main.analytics.orders",
                    "grade": "gold",
                    "owner": self._owner,
                    "description": "Unity Catalog curated orders table",
                    "refresh": {"cadence": "daily", "max_staleness_minutes": 1440},
                    "grade_rationale": "unity_catalog:gold; lineage_complete",
                    "last_audited": "2026-04-16",
                }
            )
        ]

    def fetch_verified_queries(self, since):
        del since
        return []


class _FailingConnectorAdapter:
    def __init__(self, error: Exception):
        self._error = error

    def execute_query(self, _spec):
        raise self._error


class TestConnectorRpc:
    async def test_connector_test_returns_probe_success(self, rpc_handler, mock_ws, app_state):
        app_state._connector_adapter_factory = lambda _config: _FakeConnectorAdapter()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ct1",
                "method": "connector.test",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "label": "Analytics Postgres",
                    "options": {
                        "host": "localhost",
                        "database": "analytics",
                        "schema": "public",
                        "username": "readonly_user",
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "password",
                        "password": "secret",
                    },
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["ok"] is True
        assert frame["payload"]["probe"]["kind"] == "select_1"
        assert frame["payload"]["details"]["database"] == "analytics"
        assert (
            app_state._connector_secrets.has_secret("connector/analytics_prod__probe__/credentials")
            is False
        )

    async def test_connector_save_list_and_delete(self, rpc_handler, mock_ws, app_state):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cs1",
                "method": "connector.save",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "label": "Analytics Postgres",
                    "options": {
                        "host": "localhost",
                        "database": "analytics",
                        "schema": "public",
                        "username": "readonly_user",
                        "port": 5432,
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "password",
                        "password": "secret",
                    },
                },
            }
        )

        save_frame = mock_ws.sent[0]
        assert save_frame["ok"] is True
        connector = save_frame["payload"]["connector"]
        assert connector["name"] == "analytics_prod"
        assert connector["hasCredential"] is True
        assert connector["credentialMethod"] == "secret_manager"
        assert connector["options"]["database"] == "analytics"
        assert app_state.config.connectors["analytics_prod"].options["port"] == 5432

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cl1",
                "method": "connector.list",
            }
        )
        list_frame = mock_ws.sent[1]
        assert list_frame["ok"] is True
        assert list_frame["payload"]["connectorCreationAllowed"] is True
        assert list_frame["payload"]["connectors"][0]["name"] == "analytics_prod"

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cd1",
                "method": "connector.delete",
                "params": {"name": "analytics_prod"},
            }
        )
        delete_frame = mock_ws.sent[2]
        assert delete_frame["ok"] is True
        assert delete_frame["payload"]["deleted"] is True
        assert "analytics_prod" not in app_state.config.connectors
        assert (
            app_state._connector_secrets.has_secret("connector/analytics_prod/credentials") is False
        )

    async def test_connector_save_blocked_by_org_policy(self, rpc_handler, mock_ws, app_state):
        app_state.organization_store.update_settings(connector_creation_allowed=False)

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cp1",
                "method": "connector.save",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "options": {"host": "localhost", "database": "analytics"},
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {"kind": "password", "password": "secret"},
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "disabled by organization policy" in frame["error"]["message"].lower()

    async def test_connector_test_reuses_existing_stored_secret(
        self, rpc_handler, mock_ws, app_state
    ):
        app_state._connector_adapter_factory = lambda _config: _FakeConnectorAdapter()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cs-existing",
                "method": "connector.save",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "options": {
                        "host": "localhost",
                        "database": "analytics",
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {"kind": "password", "password": "secret"},
                },
            }
        )
        mock_ws.sent.clear()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ct-existing",
                "method": "connector.test",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "options": {
                        "host": "localhost",
                        "database": "analytics",
                    },
                    "credentialMethod": "secret_manager",
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["ok"] is True
        assert frame["payload"]["probe"]["kind"] == "select_1"

    async def test_connector_test_bigquery_probe_success(self, rpc_handler, mock_ws, app_state):
        app_state._connector_adapter_factory = lambda _config: _FakeConnectorAdapter()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ct-bigquery",
                "method": "connector.test",
                "params": {
                    "name": "warehouse_bq",
                    "type": "bigquery",
                    "options": {
                        "project_id": "analytics-project",
                        "dataset": "mart",
                        "location": "asia-northeast3",
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "service_account_json",
                        "json": (
                            '{"client_email":"bot@example.com","private_key":"secret",'
                            '"token_uri":"https://oauth2.googleapis.com/token"}'
                        ),
                    },
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["ok"] is True
        assert frame["payload"]["details"]["projectId"] == "analytics-project"

    async def test_connector_test_returns_dsa_error_catalog_for_auth_failures(
        self, rpc_handler, mock_ws, app_state
    ):
        app_state._connector_adapter_factory = lambda _config: _FailingConnectorAdapter(
            PermissionError("password authentication failed for user readonly_user")
        )

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ct-auth-failure",
                "method": "connector.test",
                "params": {
                    "name": "analytics_prod",
                    "type": "postgres",
                    "options": {
                        "host": "localhost",
                        "database": "analytics",
                        "schema": "public",
                        "username": "readonly_user",
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "password",
                        "password": "secret",
                    },
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["ok"] is False
        assert frame["payload"]["errorCode"] == "DSA-AUTH-002"
        assert "[DSA-AUTH-002]" in frame["payload"]["message"]
        assert frame["payload"]["warnings"] == [
            "Reconnect the account or update the saved secret, then retry."
        ]
        assert (
            frame["payload"]["details"]["technicalMessage"]
            == "password authentication failed for user readonly_user"
        )

    async def test_connector_save_rejects_invalid_bigquery_json(
        self, rpc_handler, mock_ws, app_state
    ):
        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "cs-bigquery-invalid",
                "method": "connector.save",
                "params": {
                    "name": "warehouse_bq",
                    "type": "bigquery",
                    "options": {"project_id": "analytics-project"},
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "service_account_json",
                        "json": "not-json",
                    },
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is False
        assert "service account json is invalid" in frame["error"]["message"].lower()

    async def test_connector_test_snowflake_probe_success(self, rpc_handler, mock_ws, app_state):
        app_state._connector_adapter_factory = lambda _config: _FakeConnectorAdapter()

        await rpc_handler.handle_message(
            {
                "type": "req",
                "id": "ct-snowflake",
                "method": "connector.test",
                "params": {
                    "name": "warehouse_sf",
                    "type": "snowflake",
                    "options": {
                        "account": "xy12345.ap-northeast-2.aws",
                        "warehouse": "ANALYTICS_WH",
                        "database": "ANALYTICS",
                        "schema": "PUBLIC",
                        "username": "readonly_user",
                    },
                    "credentialMethod": "secret_manager",
                    "credentialPayload": {
                        "kind": "password",
                        "password": "secret",
                    },
                },
            }
        )

        frame = mock_ws.sent[0]
        assert frame["ok"] is True
        assert frame["payload"]["ok"] is True
        assert frame["payload"]["details"]["warehouse"] == "ANALYTICS_WH"


class TestCallbacksClose:
    """CON-05: Callback background task lifecycle."""

    async def test_close_cancels_tasks(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        # Add a long-running task
        long_task = asyncio.create_task(asyncio.sleep(100))
        cb._background_tasks.add(long_task)

        await cb.close()

        assert long_task.cancelled()
        assert len(cb._background_tasks) == 0

    async def test_emit_event_schedules_task(self, mock_ws):
        from ds_agent.api.callbacks import WsAgentCallbacks

        cb = WsAgentCallbacks(mock_ws)
        cb.emit_event("test.event", {"key": "value"})

        # Give the event loop a chance to run the task
        await asyncio.sleep(0.05)

        # Should have sent the event via websocket
        events = [f for f in mock_ws.sent if f.get("event") == "test.event"]
        assert len(events) == 1


# ---------------------------------------------------------------------------
# WebSocket token authentication (SEC-01)
# ---------------------------------------------------------------------------


class TestWsTokenAuth:
    """SEC-01: WebSocket endpoint rejects connections with missing/wrong token."""

    def test_no_auth_when_token_is_none(self, tmp_path):
        """create_app(ws_token=None) disables auth — any connection is accepted."""
        from fastapi.testclient import TestClient

        from ds_agent.api.app import create_app
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig

        app = create_app(ws_token=None)
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path / "ws")),
        )
        app.state.app_state = AppState(config=config)

        client = TestClient(app)
        # No token — should connect successfully (auth disabled)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "req", "id": "t1", "method": "status.get"})
            frame = ws.receive_json()
            assert frame["type"] == "res"
            assert frame["ok"] is True

    def test_valid_token_accepted(self, tmp_path):
        """Correct token in query param → connection accepted."""
        from fastapi.testclient import TestClient

        from ds_agent.api.app import create_app
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig

        secret = "test-secret-token-abc123"
        app = create_app(ws_token=secret)
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path / "ws")),
        )
        app.state.app_state = AppState(config=config)

        client = TestClient(app)
        with client.websocket_connect(f"/ws?token={secret}") as ws:
            ws.send_json({"type": "req", "id": "t2", "method": "status.get"})
            frame = ws.receive_json()
            assert frame["type"] == "res"
            assert frame["ok"] is True

    def test_missing_token_rejected(self, tmp_path):
        """Token required but not provided → connection closed with 1008."""
        from fastapi.testclient import TestClient

        from ds_agent.api.app import create_app
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig

        app = create_app(ws_token="required-secret")
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path / "ws")),
        )
        app.state.app_state = AppState(config=config)

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws"):
            pass

    def test_wrong_token_rejected(self, tmp_path):
        """Wrong token → connection closed with 1008."""
        from fastapi.testclient import TestClient

        from ds_agent.api.app import create_app
        from ds_agent.api.ws_handler import AppState
        from ds_agent.config.schema import AgentConfig, DSAgentConfig

        app = create_app(ws_token="correct-token")
        config = DSAgentConfig(
            agent=AgentConfig(workspace_dir=str(tmp_path / "ws")),
        )
        app.state.app_state = AppState(config=config)

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?token=wrong-token"):
            pass
