from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.application.dtos.task_contract import AssumptionInputDTO, TaskContractDraftDTO
from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.infrastructure.task_contract_container import build_task_contract_container
from ds_agent.tools.verifier_tool import run_verifier


@dataclass
class FakeProvider:
    response_text: str
    model_id: str = "gpt-5.4"
    provider_name: str = "openai"
    last_messages: list | None = None
    last_kwargs: dict[str, object] | None = None

    async def chat(self, messages, **kwargs):
        self.last_messages = messages
        self.last_kwargs = kwargs
        return LLMResponse(content=self.response_text, model=self.model_id, usage=Usage())

    async def count_tokens(self, messages) -> int:
        return 0

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider=self.provider_name,
            display_name="API Test Model",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )


def _create_contract(workspace_dir: str, session_id: str = "ws-session-1") -> str:
    return _create_contract_with_deliverables(
        workspace_dir,
        session_id=session_id,
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
    )


def _create_contract_with_deliverables(
    workspace_dir: str,
    *,
    session_id: str = "ws-session-1",
    required_deliverables: list[dict[str, str]],
) -> str:
    container = build_task_contract_container(workspace_dir)
    result = container.create.execute(
        TaskContractDraftDTO(
            session_id=session_id,
            contract_type="churn_analysis",
            business_goal="Reduce churn by one point",
            goal_brief={
                "business_question": "What drives churn?",
                "ds_problem_statement": "Binary classification",
                "comparison_baseline": "last quarter",
                "decision_to_make": "prioritize interventions",
                "expected_effort": "M",
            },
            required_deliverables=required_deliverables,
        )
    )
    return str(result["task_id"])


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        agent=AgentConfig(workspace_dir=str(tmp_path / "workspace")),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _verifier_artifacts() -> dict[str, object]:
    return {
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
    }


def test_list_task_contracts_route_returns_existing_items(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir)

    response = client.get("/api/task-contracts")

    assert response.status_code == 200
    payload = response.json()
    assert payload["contracts"][0]["task_id"] == task_id


def test_get_active_task_contract_route_filters_by_session(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir, session_id="renderer-session")

    response = client.get(
        "/api/task-contracts/active",
        params={"sessionId": "renderer-session"},
    )

    assert response.status_code == 200
    assert response.json()["contract"]["contract"]["task_id"] == task_id


def test_get_active_task_contract_route_surfaces_verifier_metadata(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir, session_id="renderer-session")

    payload = json.loads(
        asyncio.run(
            run_verifier(
                task_id=task_id,
                session_id="renderer-session",
                task_type="churn_analysis",
                business_goal="Reduce churn by one point",
                workspace_dir=workspace_dir,
                shadow_mode=True,
                run_log=[
                    {"event": "tool.call", "tool": "feature_engineer"},
                    {"event": "harness.warning", "type": "leakage", "severity": "high"},
                ],
                artifacts=_verifier_artifacts(),
            )
        )
    )

    assert payload["ok"] is True

    response = client.get(
        "/api/task-contracts/active",
        params={
            "sessionId": "renderer-session",
            "include": ["review_verdicts", "goal_brief", "delivery_pack"],
        },
    )

    assert response.status_code == 200
    contract = response.json()["contract"]
    verdict = contract["review_verdicts"][0]
    narrative_layer = next(layer for layer in verdict["layers"] if layer["layer"] == "narrative")

    assert verdict["verdict_id"] == payload["payload"]["verdict_id"]
    assert verdict["metadata"]["judge_mode"] == "heuristic_only"
    assert verdict["metadata"]["shadow_comparison_id"].startswith("SC-")
    assert isinstance(verdict["metadata"]["shadow_match_rate"], float)
    assert isinstance(verdict["metadata"]["shadow_mismatch_count"], int)
    assert narrative_layer["metadata"]["judge_mode"] == "heuristic_only"


def test_shadow_comparison_routes_return_persisted_records(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir, session_id="renderer-session")

    payload = json.loads(
        asyncio.run(
            run_verifier(
                task_id=task_id,
                session_id="renderer-session",
                task_type="churn_analysis",
                business_goal="Reduce churn by one point",
                workspace_dir=workspace_dir,
                shadow_mode=True,
                run_log=[
                    {"event": "tool.call", "tool": "feature_engineer"},
                    {"event": "harness.warning", "type": "leakage", "severity": "high"},
                ],
                artifacts=_verifier_artifacts(),
            )
        )
    )
    comparison_id = payload["payload"]["metadata"]["shadow_comparison_id"]
    verdict_id = payload["payload"]["verdict_id"]

    list_response = client.get(
        f"/api/task-contracts/{task_id}/shadow-comparisons",
        params={"verdictId": verdict_id, "mismatchesOnly": False, "limit": 5},
    )
    get_response = client.get(f"/api/task-contracts/{task_id}/shadow-comparisons/{comparison_id}")

    assert list_response.status_code == 200
    assert list_response.json()["comparisons"][0]["comparison_id"] == comparison_id
    assert get_response.status_code == 200
    assert get_response.json()["comparison"]["comparison_id"] == comparison_id


def test_update_task_contract_route_transitions_contract(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir)

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": 1,
            "patch": {},
            "transitionTo": "agreed",
            "reason": "operator agreed contract",
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "agreed"


def test_update_task_contract_route_returns_conflict_for_stale_version(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir)

    response = client.post(
        f"/api/task-contracts/{task_id}/update",
        json={
            "expectedVersion": 99,
            "patch": {},
            "transitionTo": "agreed",
        },
    )

    assert response.status_code == 409


def test_verify_assumption_route_marks_entry_verified(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir)
    container = build_task_contract_container(workspace_dir)
    added = container.add_assumption.execute(
        AssumptionInputDTO(
            task_id=task_id,
            statement="Churn means 30 inactive days",
            rationale="Dashboard convention",
            risk_level="medium",
        )
    )

    response = client.post(
        f"/api/task-contracts/{task_id}/assumptions/{added['entry_id']}/verify",
        json={
            "expectedVersion": 2,
            "verificationNote": "Matched against the dashboard definition.",
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["verified"] is True
    bundle = build_task_contract_container(workspace_dir).store.get_bundle(task_id)
    assert bundle is not None
    assert bundle.assumption_log is not None
    assert bundle.assumption_log.entries[0].verified is True


def test_build_delivery_pack_route_persists_pack(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract(workspace_dir)

    response = client.post(
        f"/api/task-contracts/{task_id}/delivery-pack/build",
        json={
            "audiences": ["executive"],
            "sourceAnalysisId": "FA-API-1",
            "globalContext": {"project": "churn_q2"},
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["status"] == "draft"
    bundle = build_task_contract_container(workspace_dir).store.get_bundle(task_id)
    assert bundle is not None
    assert bundle.delivery_pack is not None
    assert bundle.delivery_pack.source_analysis_id == "FA-API-1"
    assert bundle.delivery_pack.global_context["project"] == "churn_q2"


def test_render_and_dispatch_delivery_routes_round_trip(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract_with_deliverables(
        workspace_dir,
        required_deliverables=[{"type": "pm_action_memo", "audience": "pm", "format": "markdown"}],
    )

    build_response = client.post(
        f"/api/task-contracts/{task_id}/delivery-pack/build",
        json={"audiences": ["pm"]},
    )
    artifact_id = build_response.json()["result"]["artifact_ids"][0]

    render_response = client.post(
        f"/api/task-contracts/{task_id}/delivery-artifacts/{artifact_id}/render",
        json={
            "analysis": {
                "summary": "Churn increased in premium cohorts.",
                "recommendation": "Launch a retention pilot.",
            },
            "outputDir": str(tmp_path / "artifacts"),
        },
    )

    assert render_response.status_code == 200
    render_payload = render_response.json()["result"]
    assert render_payload["pack_status"] == "rendered"
    assert Path(render_payload["output_path"]).exists()

    dispatch_response = client.post(
        f"/api/task-contracts/{task_id}/delivery/dispatch",
        json={
            "artifactIds": [artifact_id],
            "approveManualReview": True,
        },
    )

    assert dispatch_response.status_code == 200
    dispatch_payload = dispatch_response.json()["result"]
    assert dispatch_payload["dispatch_status"] == "dispatched"
    assert dispatch_payload["pack_status"] == "dispatched"

    log_response = client.get(
        f"/api/task-contracts/{task_id}/delivery/log",
        params={"artifactId": artifact_id, "limit": 10},
    )

    assert log_response.status_code == 200
    log_payload = log_response.json()["result"]
    assert log_payload["returned"] == 2
    assert log_payload["summary"]["pack_status"] == "dispatched"
    assert log_payload["summary"]["artifact_count"] == 1
    assert log_payload["summary"]["sent"] == 2
    assert all(entry["artifact_id"] == artifact_id for entry in log_payload["records"])


def test_render_delivery_route_supports_provider_backed_opt_in(tmp_path) -> None:
    client = _client(tmp_path)
    workspace_dir = str(client.app.state.app_state.config.agent.workspace_dir)
    task_id = _create_contract_with_deliverables(
        workspace_dir,
        required_deliverables=[{"type": "pm_action_memo", "audience": "pm", "format": "markdown"}],
    )

    build_response = client.post(
        f"/api/task-contracts/{task_id}/delivery-pack/build",
        json={"audiences": ["pm"]},
    )
    artifact_id = build_response.json()["result"]["artifact_ids"][0]
    provider = FakeProvider(
        """
        {
          "blocks": [
            {
              "section": "summary",
              "title": "Summary",
              "body_md": "Premium cohorts drove the churn spike.",
              "citations": ["lineage-1"]
            }
          ],
          "overall_tone": "actionable",
          "flagged_claims": []
        }
        """
    )
    model_name = "openai/gpt-5.4"

    with patch(
        "ds_agent.api.routes.task_contracts.create_provider_router",
        return_value=provider,
    ) as mock_router:
        render_response = client.post(
            f"/api/task-contracts/{task_id}/delivery-artifacts/{artifact_id}/render",
            json={
                "analysis": {
                    "summary": "Churn increased in premium cohorts.",
                    "recommendation": "Launch a retention pilot.",
                },
                "outputDir": str(tmp_path / "provider-artifacts"),
                "providerBacked": True,
                "model": model_name,
            },
        )

    assert render_response.status_code == 200
    payload = render_response.json()["result"]
    mock_router.assert_called_once_with(
        model_name,
        client.app.state.app_state.config,
        token_store=client.app.state.app_state.token_store,
    )
    assert payload["renderer_mode"] == "provider-backed"
    assert payload["renderer_model"] == model_name
    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}


def test_render_delivery_route_rejects_model_without_provider_backed(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/task-contracts/TC-ignored/delivery-artifacts/DA-ignored/render",
        json={
            "analysis": {"summary": "ignored"},
            "outputDir": str(tmp_path / "ignored"),
            "model": "openai/gpt-5.4",
        },
    )

    assert response.status_code == 422
