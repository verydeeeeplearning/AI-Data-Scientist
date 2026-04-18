from __future__ import annotations

import asyncio
import json

from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.infrastructure.verifier_container import build_verifier_container
from ds_agent.tools.verifier_tool import (
    get_review_verdict,
    get_verifier_shadow_comparison,
    list_verifier_shadow_comparisons,
    run_verifier,
)


def test_run_verifier_tool_persists_and_loads_verdict(tmp_path) -> None:
    result = asyncio.run(
        run_verifier(
            task_id="TC-2026-001",
            session_id="session-1",
            task_type="churn_analysis",
            business_goal="Reduce churn",
            workspace_dir=str(tmp_path),
            artifacts={
                "train_df": {
                    "id": [1, 2, 3, 4],
                    "feature_a": [0.1, 0.2, 0.3, 0.4],
                    "feature_b": [1.0, 0.8, 0.5, 0.3],
                    "target": [0, 0, 1, 1],
                },
                "val_df": {
                    "id": [5, 6],
                    "feature_a": [0.15, 0.35],
                    "feature_b": [0.9, 0.4],
                    "target": [0, 1],
                },
                "target_column": "target",
                "subgroup_metrics": {"a": 0.82, "b": 0.80},
                "overall_metric": 0.81,
                "actual_metric": 0.82,
                "baseline_metric": 0.70,
                "baseline_p_value": 0.01,
                "sample_size": 200,
                "required_sample_size": 120,
                "effect_size": 0.2,
                "actual_accuracy": 0.83,
                "majority_accuracy": 0.55,
                "model_family": "linear",
                "interpret_coefficients": True,
                "vif": {"feature_a": 2.0, "feature_b": 3.0},
                "train_metric": 0.84,
                "val_metric": 0.80,
                "p_values": [0.01, 0.02],
                "claims_adjusted": True,
                "min_practical_effect": 0.05,
                "current_df": {
                    "customer_id": [1, 2, 3],
                    "segment": ["a", "a", "b"],
                    "score": [0.1, 0.2, 0.3],
                    "event_at": [
                        "2026-04-16T09:00:00Z",
                        "2026-04-16T09:15:00Z",
                        "2026-04-16T09:30:00Z",
                    ],
                },
                "observed_df": {
                    "customer_id": [1, 2, 3],
                    "segment": ["a", "a", "b"],
                    "score": [0.1, 0.2, 0.3],
                    "event_at": [
                        "2026-04-16T09:00:00Z",
                        "2026-04-16T09:15:00Z",
                        "2026-04-16T09:30:00Z",
                    ],
                },
                "reference_df": {
                    "score": [0.1, 0.2, 0.3],
                },
                "data_schema": {
                    "customer_id": {"dtype": "int64", "required": True},
                    "segment": {"dtype": "object", "required": True},
                    "score": {"dtype": "float64", "required": True},
                },
                "temporal_column": "event_at",
                "reference_now": "2026-04-16T10:00:00Z",
                "sla_max_staleness_seconds": 7200,
                "data_profile": {
                    "columns": {
                        "segment": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                        "score": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                    }
                },
                "deliverable_payload": {"summary": "All clear"},
                "cost_budget_usd": 10.0,
                "retention_items": [
                    {
                        "artifact": "report.md",
                        "retention_label": "30d",
                        "storage_retention": "30d",
                    }
                ],
                "narrative": "Accuracy improved to 0.82.",
                "metrics": {"accuracy": 0.82},
            },
        )
    )
    payload = json.loads(result)

    assert payload["ok"] is True
    verdict_id = payload["payload"]["verdict_id"]

    loaded = json.loads(
        asyncio.run(get_review_verdict(verdict_id=verdict_id, workspace_dir=str(tmp_path)))
    )

    assert loaded["ok"] is True
    assert loaded["payload"]["verdict_id"] == verdict_id


def test_run_verifier_tool_records_into_existing_task_contract(tmp_path) -> None:
    task_contracts = build_task_contract_container(str(tmp_path))
    task_contracts.create.execute(
        TaskContractDraftDTO(
            session_id="session-1",
            contract_type="churn_analysis",
            business_goal="Reduce churn",
            goal_brief={
                "business_question": "Why churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize actions",
                "expected_effort": "M",
            },
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"}
            ],
            definition_of_done={
                "criteria": ["Verifier must run before close"],
                "verifier": {"min_confidence_grade": "medium"},
            },
        )
    )
    created = task_contracts.list_contracts.execute("session-1")[0]

    result = asyncio.run(
        run_verifier(
            task_id=created.task_id,
            session_id="session-1",
            task_type="churn_analysis",
            business_goal="Reduce churn",
            workspace_dir=str(tmp_path),
            artifacts={
                "train_df": {
                    "id": [1, 2, 3, 4],
                    "feature_a": [0.1, 0.2, 0.3, 0.4],
                    "feature_b": [1.0, 0.8, 0.5, 0.3],
                    "target": [0, 0, 1, 1],
                },
                "val_df": {
                    "id": [5, 6],
                    "feature_a": [0.15, 0.35],
                    "feature_b": [0.9, 0.4],
                    "target": [0, 1],
                },
                "target_column": "target",
                "subgroup_metrics": {"a": 0.82, "b": 0.80},
                "overall_metric": 0.81,
                "actual_metric": 0.82,
                "baseline_metric": 0.70,
                "baseline_p_value": 0.01,
                "sample_size": 200,
                "required_sample_size": 120,
                "effect_size": 0.2,
                "actual_accuracy": 0.83,
                "majority_accuracy": 0.55,
                "model_family": "linear",
                "interpret_coefficients": True,
                "vif": {"feature_a": 2.0, "feature_b": 3.0},
                "train_metric": 0.84,
                "val_metric": 0.80,
                "p_values": [0.01, 0.02],
                "claims_adjusted": True,
                "min_practical_effect": 0.05,
                "current_df": {
                    "customer_id": [1, 2, 3],
                    "segment": ["a", "a", "b"],
                    "score": [0.1, 0.2, 0.3],
                    "event_at": [
                        "2026-04-16T09:00:00Z",
                        "2026-04-16T09:15:00Z",
                        "2026-04-16T09:30:00Z",
                    ],
                },
                "observed_df": {
                    "customer_id": [1, 2, 3],
                    "segment": ["a", "a", "b"],
                    "score": [0.1, 0.2, 0.3],
                    "event_at": [
                        "2026-04-16T09:00:00Z",
                        "2026-04-16T09:15:00Z",
                        "2026-04-16T09:30:00Z",
                    ],
                },
                "reference_df": {"score": [0.1, 0.2, 0.3]},
                "data_schema": {
                    "customer_id": {"dtype": "int64", "required": True},
                    "segment": {"dtype": "object", "required": True},
                    "score": {"dtype": "float64", "required": True},
                },
                "temporal_column": "event_at",
                "reference_now": "2026-04-16T10:00:00Z",
                "sla_max_staleness_seconds": 7200,
                "data_profile": {
                    "columns": {
                        "segment": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                        "score": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                    }
                },
                "deliverable_payload": {"summary": "All clear"},
                "cost_budget_usd": 10.0,
                "retention_items": [
                    {
                        "artifact": "report.md",
                        "retention_label": "30d",
                        "storage_retention": "30d",
                    }
                ],
                "narrative": "Accuracy improved to 0.82.",
                "metrics": {"accuracy": 0.82},
            },
        )
    )
    payload = json.loads(result)
    bundle = task_contracts.store.get_bundle(created.task_id)

    assert payload["ok"] is True
    assert payload["task_contract_recorded"] is True
    assert bundle is not None
    assert bundle.review_verdicts
    assert bundle.review_verdicts[0].verdict_id == payload["payload"]["verdict_id"]


def test_run_verifier_tool_records_shadow_comparison_when_hook_log_present(tmp_path) -> None:
    result = asyncio.run(
        run_verifier(
            task_id="TC-2026-001",
            session_id="session-1",
            task_type="churn_analysis",
            business_goal="Reduce churn",
            workspace_dir=str(tmp_path),
            shadow_mode=True,
            run_log=[
                {"event": "tool.call", "tool": "feature_engineer"},
                {"event": "tool.call", "tool": "train_model"},
                {"event": "harness.warning", "type": "leakage", "severity": "high"},
            ],
            artifacts={
                "train_df": {
                    "id": [1, 2, 3, 4],
                    "feature_a": [0.1, 0.2, 0.3, 0.4],
                    "target": [0, 0, 1, 1],
                },
                "val_df": {
                    "id": [1, 5],
                    "feature_a": [0.15, 0.35],
                    "target": [0, 1],
                },
                "target_column": "target",
                "actual_metric": 0.82,
                "baseline_metric": 0.70,
                "baseline_p_value": 0.01,
                "sample_size": 200,
                "required_sample_size": 120,
                "effect_size": 0.2,
                "current_df": {"score": [0.1, 0.2, 0.3]},
                "observed_df": {"score": [0.1, 0.2, 0.3]},
                "reference_df": {"score": [0.1, 0.2, 0.3]},
                "deliverable_payload": {"summary": "All clear"},
                "narrative": "Accuracy improved to 0.82.",
                "metrics": {"accuracy": 0.82},
            },
        )
    )
    payload = json.loads(result)
    metadata = payload["payload"]["metadata"]
    shadow_records = build_verifier_container(
        str(tmp_path)
    ).shadow_repo.list_for_task("TC-2026-001")

    assert payload["ok"] is True
    assert payload["shadow_mode"] is True
    assert metadata["shadow_comparison_id"].startswith("SC-")
    assert shadow_records


def test_shadow_comparison_tools_load_and_list_persisted_records(tmp_path) -> None:
    payload = json.loads(
        asyncio.run(
            run_verifier(
                task_id="TC-2026-001",
                session_id="session-1",
                task_type="churn_analysis",
                business_goal="Reduce churn",
                workspace_dir=str(tmp_path),
                shadow_mode=True,
                run_log=[
                    {"event": "tool.call", "tool": "feature_engineer"},
                    {"event": "harness.warning", "type": "leakage", "severity": "high"},
                ],
                artifacts={
                    "train_df": {
                        "id": [1, 2, 3, 4],
                        "feature_a": [0.1, 0.2, 0.3, 0.4],
                        "target": [0, 0, 1, 1],
                    },
                    "val_df": {
                        "id": [1, 5],
                        "feature_a": [0.15, 0.35],
                        "target": [0, 1],
                    },
                    "target_column": "target",
                    "actual_metric": 0.82,
                    "baseline_metric": 0.70,
                    "baseline_p_value": 0.01,
                    "sample_size": 200,
                    "required_sample_size": 120,
                    "effect_size": 0.2,
                    "current_df": {"score": [0.1, 0.2, 0.3]},
                    "observed_df": {"score": [0.1, 0.2, 0.3]},
                    "reference_df": {"score": [0.1, 0.2, 0.3]},
                    "deliverable_payload": {"summary": "All clear"},
                    "narrative": "Accuracy improved to 0.82.",
                    "metrics": {"accuracy": 0.82},
                },
            )
        )
    )

    comparison_id = payload["payload"]["metadata"]["shadow_comparison_id"]
    verdict_id = payload["payload"]["verdict_id"]

    loaded = json.loads(
        asyncio.run(
            get_verifier_shadow_comparison(
                comparison_id=comparison_id,
                workspace_dir=str(tmp_path),
            )
        )
    )
    listed = json.loads(
        asyncio.run(
            list_verifier_shadow_comparisons(
                verdict_id=verdict_id,
                workspace_dir=str(tmp_path),
                mismatches_only=False,
            )
        )
    )

    assert loaded["ok"] is True
    assert loaded["payload"]["comparison_id"] == comparison_id
    assert listed["ok"] is True
    assert listed["items"][0]["comparison_id"] == comparison_id
