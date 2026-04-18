"""Seed an isolated Decision OS workspace for Electron E2E review-flow tests."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.config.loader import save_config
from ds_agent.config.schema import DSAgentConfig
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.model import Model
from ds_agent.domain.entities.post_deploy import PostDeployMonitorState
from ds_agent.domain.entities.review_artifact import build_review_artifact
from ds_agent.infrastructure.persistence.deploy_monitor_state_store import (
    SqliteDeployMonitorStateStore,
)
from ds_agent.infrastructure.persistence.model_registry_store import SqliteModelRegistryStore
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.runtime.session_registry import RuntimeSessionRegistry
from ds_agent.runtime.transcript_store import JsonTranscriptStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home-dir")
    parser.add_argument("--config-path")
    parser.add_argument("--workspace-dir", required=True)
    parser.add_argument("--session-id", default="decision-os-review-session")
    args = parser.parse_args()
    if not args.home_dir and not args.config_path:
        parser.error("either --home-dir or --config-path is required")
    return args


def _resolve_config_path(args: argparse.Namespace) -> Path:
    if args.config_path:
        return Path(args.config_path).expanduser().resolve()
    home_dir = Path(args.home_dir).expanduser().resolve()
    return home_dir / ".ds-agent" / "config.yaml"


def _seed_config(config_path: Path, workspace_dir: Path) -> None:
    config = DSAgentConfig()
    config.agent.workspace_dir = str(workspace_dir)
    config.gateway.autonomous_runtime_enabled = False
    save_config(config, config_path)


def _seed_runtime_session(workspace_dir: Path, session_id: str) -> None:
    RuntimeSessionRegistry(str(workspace_dir)).ensure(session_id, "electron")
    JsonTranscriptStore(str(workspace_dir)).replace_messages(
        session_id,
        [
            ChatMessage(
                role=Role.USER,
                content="Open the Decision OS review surface for the latest churn candidate.",
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Seeded Decision OS review workspace is ready.",
            ),
        ],
    )


def _seed_experiment_runs(workspace_dir: Path) -> None:
    experiment_log = ExperimentLog(
        data_dir=str(workspace_dir / "data" / "memory" / "experiment_log")
    )
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
                "result": {"metrics": {"f1_macro": 0.8, "fp_rate": 0.12}},
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
                    "rationale": "Tune the learning rate and refresh the activity feature.",
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
                "result": {"metrics": {"f1_macro": 0.84, "fp_rate": 0.1}},
                "verifier_summary": {
                    "statistical": "PASS",
                    "data": "PASS",
                    "policy": "PASS",
                },
                "verifier_findings": ["monitor feature freshness after promotion"],
                "created_at": datetime(2026, 4, 16, 10, tzinfo=UTC),
                "owner": "growth-ds",
                "status": "succeeded",
                "promotion_state": "candidate",
                "reproducibility_status": "reproduced",
                "review_artifacts": [
                    build_review_artifact(
                        skill_name="backtesting",
                        summary="Time-split backtesting remained stable across the recent folds.",
                        artifact={
                            "folds": [
                                {
                                    "fold_label": "fold-1",
                                    "metric": "f1_macro",
                                    "score": 0.83,
                                    "baseline_score": 0.8,
                                    "status": "pass",
                                },
                                {
                                    "fold_label": "fold-2",
                                    "metric": "f1_macro",
                                    "score": 0.84,
                                    "baseline_score": 0.81,
                                    "status": "pass",
                                },
                            ],
                            "consistency_score": 0.92,
                            "warnings": [],
                        },
                        narrative=(
                            "Backtesting suggests the uplift is stable enough for staging review."
                        ),
                        artifact_id="review-backtest-001",
                        created_at=datetime(2026, 4, 16, 10, 5, tzinfo=UTC),
                    ).model_dump(mode="json"),
                    build_review_artifact(
                        skill_name="retrain-vs-rollback",
                        summary=(
                            "If the candidate degrades in production, rollback "
                            "is safer than retrain."
                        ),
                        artifact={
                            "recommendation": "rollback",
                            "rationale": (
                                "Observed drift and metric loss exceed rollback thresholds."
                            ),
                            "evidence": ["psi=0.33", "f1_macro=-0.14"],
                        },
                        narrative="Use the existing champion until retraining is complete.",
                        artifact_id="review-rvr-001",
                        created_at=datetime(2026, 4, 16, 10, 10, tzinfo=UTC),
                    ).model_dump(mode="json"),
                ],
            }
        )
    )


def _seed_models(workspace_dir: Path) -> None:
    model_store = SqliteModelRegistryStore.for_workspace(str(workspace_dir))
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


def _seed_post_deploy_state(workspace_dir: Path) -> None:
    deploy_store = SqliteDeployMonitorStateStore.for_workspace(str(workspace_dir))
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
                        "baseline_value": 0.8,
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


def _seed_rollback_plan(workspace_dir: Path) -> None:
    rollback_plan = workspace_dir / "registry" / "rollback" / "churn.yaml"
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


def main() -> None:
    args = _parse_args()
    config_path = _resolve_config_path(args)
    workspace_dir = Path(args.workspace_dir).expanduser().resolve()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    _seed_config(config_path, workspace_dir)
    _seed_runtime_session(workspace_dir, args.session_id)
    _seed_experiment_runs(workspace_dir)
    _seed_models(workspace_dir)
    _seed_post_deploy_state(workspace_dir)
    _seed_rollback_plan(workspace_dir)

    print(
        "seeded "
        f"config={config_path} workspace={workspace_dir} "
        f"session={args.session_id} review_flow=decision_os"
    )


if __name__ == "__main__":
    main()
