from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from ds_agent.api.agent_session_registry import SessionRecord
from ds_agent.api.app import create_app
from ds_agent.api.ws_handler import AppState
from ds_agent.config.schema import AgentConfig, DSAgentConfig, ProviderConfig
from ds_agent.domain.entities.dataset_manifest import DatasetEntry, DatasetManifest
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.task_contract import DefinitionOfDone, TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.goal_store import JsonGoalStore


class _FakeBudget:
    def get_summary(self) -> dict[str, float]:
        return {
            "total_cost_usd": 4.2,
            "max_cost_usd": 10.0,
            "wall_time_seconds": 61.0,
        }


class _FakeModelInfo:
    model_id = "anthropic/claude-sonnet-4-6"


class _FakeProvider:
    def get_model_info(self) -> _FakeModelInfo:
        return _FakeModelInfo()


class _FakeAgent:
    _budget = _FakeBudget()
    _provider = _FakeProvider()


def _client(tmp_path) -> TestClient:
    app = create_app()
    config = DSAgentConfig(
        provider=ProviderConfig(
            default_model="anthropic/claude-sonnet-4-6",
            fallback_models=["openai/gpt-4.1-mini"],
            max_budget_usd=10.0,
            budget_warning_threshold_pct=80.0,
        ),
        agent=AgentConfig(
            workspace_dir=str(tmp_path / "workspace"),
            mode="supervised",
            language="en",
        ),
    )
    app.state.app_state = AppState(config=config)
    return TestClient(app)


def _seed_bundle(client: TestClient, *, session_id: str) -> None:
    now = datetime(2026, 4, 19, tzinfo=UTC)
    bundle = TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-002",
            session_id=session_id,
            type="churn_analysis",
            status="in_progress",
            business_goal="Reduce churn in the subscription funnel",
            authority="supervised",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "dashboard", "audience": "pm", "format": "link"},
            ],
            definition_of_done=DefinitionOfDone(
                criteria=["Produce a segment-level churn summary."]
            ),
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id="GB-2",
            task_id="TC-2026-002",
            business_question="Why are subscriptions churning?",
            ds_problem_statement="Explain segment-level churn drivers.",
            comparison_baseline="last month",
            decision_to_make="Choose the next retention intervention",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        dataset_manifest=DatasetManifest(
            manifest_id="DM-2",
            task_id="TC-2026-002",
            entries=[DatasetEntry(dataset_ref="uploads/churn.csv", row_count=321)],
            total_rows=321,
            generated_at=now,
        ),
    ).sync_references()

    workspace_dir = client.app.state.app_state.config.agent.workspace_dir
    SqliteTaskContractStore.for_workspace(workspace_dir).create_bundle(bundle)


def test_mission_route_returns_aggregated_context(tmp_path) -> None:
    client = _client(tmp_path)
    session_id = "session-1"
    _seed_bundle(client, session_id=session_id)

    workspace_dir = client.app.state.app_state.config.agent.workspace_dir
    JsonGoalStore(workspace_dir).ensure_from_message(
        session_id,
        "Investigate subscription churn",
        run_id="run-1",
    )
    client.app.state.app_state._sessions._agents[session_id] = SessionRecord(  # type: ignore[attr-defined]
        agent=_FakeAgent(),
        model_name="anthropic/claude-sonnet-4-6",
        authority_mode="supervised",
    )

    response = client.get(f"/api/mission/current?sessionId={session_id}")

    assert response.status_code == 200
    mission = response.json()["mission"]
    assert mission["goal"]["title"] == "Reduce churn in the subscription funnel"
    assert mission["goal"]["successCriteria"] == ["Produce a segment-level churn summary."]
    assert mission["dataSources"] == [
        {"type": "file", "label": "uploads/churn.csv", "rowCount": 321}
    ]
    assert mission["deliverables"] == ["exec_brief", "dashboard"]
    assert mission["constraints"] == {
        "language": "en",
        "requiresApproval": True,
        "localOnlyModel": False,
    }
    assert mission["stage"] == {
        "current": 2,
        "total": 4,
        "label": "Execution in progress",
    }
    assert mission["mode"] == "supervised"
    assert mission["model"]["primary"] == "anthropic/claude-sonnet-4-6"
    assert mission["budget"] == {
        "spentUsd": 4.2,
        "limitUsd": 10.0,
        "elapsedSec": 61.0,
        "nearLimit": False,
    }
    assert mission["connection"]["state"] == "connected"
    assert mission["connection"]["latencyMs"] is None


def test_mission_route_returns_default_context_for_unknown_session(tmp_path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/mission/current?sessionId=unknown-session")

    assert response.status_code == 200
    mission = response.json()["mission"]
    assert mission["goal"] == {"title": "No active mission", "successCriteria": []}
    assert mission["dataSources"] == []
    assert mission["deliverables"] == []
    assert mission["stage"] == {"current": 1, "total": 4, "label": "Ready"}
    assert mission["mode"] == "supervised"
    assert mission["model"]["primary"] == "anthropic/claude-sonnet-4-6"
    assert mission["budget"] == {
        "spentUsd": 0.0,
        "limitUsd": 10.0,
        "elapsedSec": 0.0,
        "nearLimit": False,
    }
    assert mission["connection"]["state"] == "disconnected"
