from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ds_agent.agent.builtin_hooks import ReviewArtifactCaptureHook
from ds_agent.agent.core import DSAgent
from ds_agent.agent.hooks import HookContext, HookRegistry
from ds_agent.application.services.review_artifact_capture import (
    extract_review_artifact_captures,
)
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.memory.experiment_log import ExperimentLog


def _experiment_run(run_id: str) -> ExperimentRun:
    return ExperimentRun.model_validate(
        {
            "run_id": run_id,
            "experiment_group": "decision-os",
            "sequence": 1,
            "hypothesis": {
                "statement": "Use LightGBM candidate.",
                "rationale": "Candidate improved validation stability.",
                "expected_effect": "Lift f1_macro.",
            },
            "method": {
                "model_family": "lightgbm",
                "hyperparameters": {"num_leaves": 64},
                "code_ref": "git:abc123",
            },
            "feature_refs": [],
            "data_snapshot_uri": "snapshot://churn/2026-04-16",
            "result": {
                "metrics": {"f1_macro": 0.82},
                "plots": [],
            },
            "created_at": datetime.now(UTC),
            "owner": "ds-agent",
        }
    )


def _capture_comment(run_id: str) -> str:
    payload = {
        "artifacts": [
            {
                "run_id": run_id,
                "skill_name": "retrain-vs-rollback",
                "summary": "Recommend retraining instead of rollback.",
                "narrative": "PSI is elevated but business KPI loss is still recoverable.",
                "artifact": {
                    "recommendation": "retrain",
                    "rationale": "Drift is elevated without catastrophic KPI loss.",
                    "evidence": ["psi=0.17", "conversion_rate_drop=0.03"],
                },
            }
        ]
    }
    return f"<!-- DS_REVIEW_ARTIFACTS {json.dumps(payload)} -->"


def test_extract_review_artifact_captures_strips_hidden_block() -> None:
    response = "Visible Decision OS summary.\n\n" + _capture_comment("run-candidate")

    parsed = extract_review_artifact_captures(response)

    assert parsed.cleaned_response == "Visible Decision OS summary."
    assert parsed.errors == []
    assert len(parsed.captures) == 1
    assert parsed.captures[0].run_id == "run-candidate"
    assert parsed.captures[0].skill_name == "retrain-vs-rollback"


@pytest.mark.asyncio
async def test_review_artifact_capture_hook_persists_to_experiment_log(tmp_path) -> None:
    workspace = tmp_path
    experiment_log = ExperimentLog(data_dir=str(workspace / "data" / "memory" / "experiment_log"))
    experiment_log.record_extended(_experiment_run("run-candidate"))
    hook = ReviewArtifactCaptureHook(str(workspace))

    result = await hook.on_final_response(
        "Visible Decision OS summary.\n\n" + _capture_comment("run-candidate"),
        HookContext(session_id="session-1", run_id="runtime-run-1"),
    )

    stored = experiment_log.get_run("run-candidate")
    assert result.modified_response == "Visible Decision OS summary."
    assert stored is not None
    assert len(stored.review_artifacts) == 1
    assert stored.review_artifacts[0].skill_name == "retrain-vs-rollback"
    assert stored.review_artifacts[0].artifact.recommendation == "retrain"


@pytest.mark.asyncio
async def test_agent_finalizes_with_clean_response_and_persists_review_artifact(
    tmp_path,
    make_mock_provider,
    make_mock_tool_registry,
) -> None:
    workspace = tmp_path
    experiment_log = ExperimentLog(data_dir=str(workspace / "data" / "memory" / "experiment_log"))
    experiment_log.record_extended(_experiment_run("run-candidate"))
    provider = make_mock_provider(
        [
            LLMResponse(
                content=("Visible Decision OS summary.\n\n" + _capture_comment("run-candidate")),
                usage=Usage(input_tokens=12, output_tokens=8),
            )
        ]
    )
    hooks = HookRegistry()
    hooks.register(ReviewArtifactCaptureHook(str(workspace)))
    agent = DSAgent(
        provider=provider,
        tool_registry=make_mock_tool_registry(),
        hook_registry=hooks,
        session_id="session-2",
    )
    agent.set_runtime_context("runtime-run-2")

    result = await agent.run("Summarize the Decision OS recommendation for run-candidate.")

    stored = experiment_log.get_run("run-candidate")
    assert result == "Visible Decision OS summary."
    assert stored is not None
    assert len(stored.review_artifacts) == 1
    assert stored.review_artifacts[0].summary == "Recommend retraining instead of rollback."
