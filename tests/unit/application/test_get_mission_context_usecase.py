from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.usecases.get_mission_context_usecase import GetMissionContextUseCase
from ds_agent.config.schema import AgentConfig, DSAgentConfig, ProviderConfig
from ds_agent.domain.entities.dataset_manifest import DatasetEntry, DatasetManifest
from ds_agent.domain.entities.goal import GoalRecord, GoalStatus
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.runtime_state import RunState, RuntimeStatus
from ds_agent.domain.entities.task_contract import DefinitionOfDone, TaskContract
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle


class _FakeBudget:
    def get_summary(self) -> dict[str, float]:
        return {
            "total_cost_usd": 8.1,
            "max_cost_usd": 10.0,
            "wall_time_seconds": 95.5,
        }


class _FakeModelInfo:
    model_id = "anthropic/claude-sonnet-4-6"


class _FakeProvider:
    def get_model_info(self) -> _FakeModelInfo:
        return _FakeModelInfo()


class _FakeAgent:
    _budget = _FakeBudget()
    _provider = _FakeProvider()


def _config(
    *,
    model: str = "anthropic/claude-sonnet-4-6",
    mode: str = "supervised",
) -> DSAgentConfig:
    return DSAgentConfig(
        provider=ProviderConfig(
            default_model=model,
            fallback_models=["openai/gpt-4.1-mini"],
            max_budget_usd=10.0,
            budget_warning_threshold_pct=80.0,
        ),
        agent=AgentConfig(
            workspace_dir="C:/tmp/workspace",
            mode=mode,
            language="en",
        ),
    )


def _bundle() -> TaskContractBundle:
    now = datetime(2026, 4, 19, tzinfo=UTC)
    return TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="churn_analysis",
            status="in_progress",
            business_goal="Reduce churn in the SME retention funnel",
            authority="supervised",
            audience="senior_staff",
            required_deliverables=[
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
                {"type": "dashboard", "audience": "pm", "format": "link"},
                {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            ],
            definition_of_done=DefinitionOfDone(
                criteria=[
                    "Quantify the churn drivers by segment.",
                    "Recommend the next retention intervention.",
                ]
            ),
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id="GB-1",
            task_id="TC-2026-001",
            business_question="Why is churn rising?",
            ds_problem_statement="Estimate churn drivers and next actions.",
            comparison_baseline="last quarter",
            decision_to_make="Select the next retention action",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        dataset_manifest=DatasetManifest(
            manifest_id="DM-1",
            task_id="TC-2026-001",
            entries=[
                DatasetEntry(dataset_ref="retention/customers.csv", row_count=1200),
                DatasetEntry(dataset_ref="warehouse.analytics.customer_events", row_count=4500),
            ],
            total_rows=5700,
            generated_at=now,
        ),
    ).sync_references()


def test_get_mission_context_usecase_combines_contract_goal_run_and_agent_state() -> None:
    goal = GoalRecord(
        goal_id="goal-1",
        session_id="session-1",
        summary="Investigate churn rise",
        detail="Find the segments driving churn and propose the next action.",
        status=GoalStatus.IN_PROGRESS,
    )
    latest_run = RunState(
        run_id="run-1",
        session_id="session-1",
        surface="ws",
        message="Analyze churn",
        status=RuntimeStatus.RUNNING,
        cost_usd=2.2,
    )

    result = GetMissionContextUseCase(_config()).execute(
        session_id="session-1",
        task_contract_bundle=_bundle(),
        active_goal=goal,
        latest_run=latest_run,
        active_agent=_FakeAgent(),
    )

    assert result.goal.title == "Reduce churn in the SME retention funnel"
    assert result.goal.success_criteria == [
        "Quantify the churn drivers by segment.",
        "Recommend the next retention intervention.",
    ]
    assert [source.label for source in result.data_sources] == [
        "retention/customers.csv",
        "warehouse.analytics.customer_events",
    ]
    assert [source.type for source in result.data_sources] == ["file", "database"]
    assert result.deliverables == ["exec_brief", "dashboard"]
    assert result.constraints.language == "en"
    assert result.constraints.requires_approval is True
    assert result.constraints.local_only_model is False
    assert result.stage.current == 2
    assert result.stage.label == "Analysis running"
    assert result.mode == "supervised"
    assert result.model.primary == "anthropic/claude-sonnet-4-6"
    assert result.model.fallbacks == ["openai/gpt-4.1-mini"]
    assert result.model.capabilities == ["balanced_reasoning", "recommended_default"]
    assert result.budget.spent_usd == 8.1
    assert result.budget.limit_usd == 10.0
    assert result.budget.elapsed_sec == 95.5
    assert result.budget.near_limit is True
    assert result.connection.state == "connected"


def test_get_mission_context_usecase_falls_back_without_contract_or_agent() -> None:
    goal = GoalRecord(
        goal_id="goal-2",
        session_id="session-2",
        summary="Profile the uploaded leads file",
        detail="Understand schema quality before modeling.",
        status=GoalStatus.BLOCKED,
    )
    latest_run = RunState(
        run_id="run-2",
        session_id="session-2",
        surface="ws",
        message="Profile leads.csv",
        status=RuntimeStatus.FAILED,
        started_at=10.0,
        finished_at=18.5,
        cost_usd=1.25,
    )

    result = GetMissionContextUseCase(_config(model="ollama/llama3.2", mode="auto")).execute(
        session_id="session-2",
        task_contract_bundle=None,
        active_goal=goal,
        latest_run=latest_run,
        active_agent=None,
    )

    assert result.goal.title == "Profile the uploaded leads file"
    assert result.goal.success_criteria == []
    assert result.data_sources == []
    assert result.deliverables == []
    assert result.constraints.requires_approval is False
    assert result.constraints.local_only_model is True
    assert result.stage.current == 3
    assert result.stage.label == "Blocked"
    assert result.model.primary == "ollama/llama3.2"
    assert result.model.capabilities == ["local_execution", "offline_ready"]
    assert result.budget.spent_usd == 1.25
    assert result.budget.limit_usd == 10.0
    assert result.budget.elapsed_sec == 8.5
    assert result.budget.near_limit is False
    assert result.connection.state == "disconnected"
