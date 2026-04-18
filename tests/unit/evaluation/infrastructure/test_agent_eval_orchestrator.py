from __future__ import annotations

from dataclasses import dataclass

from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.infrastructure.orchestrator.agent_eval_orchestrator import (
    AgentEvalOrchestrator,
)


def _task(task_id: str = "retail.live_bridge.v1") -> GoldTask:
    return GoldTask.model_validate(
        {
            "id": task_id,
            "task_version": 1,
            "domain": "retail",
            "difficulty": "easy",
            "prompt": "Assess churn risk for the premium cohort and summarize the next action.",
            "input": {
                "datasets": [{"name": "premium_customers", "source": "fixtures/premium.csv"}],
                "budget_usd": 5.0,
                "time_budget_min": 15,
            },
            "expected_deliverables": [
                {
                    "type": "goal_brief",
                    "must_contain": ["problem_framing", "kpi_definition"],
                },
                {"type": "executive_summary"},
            ],
            "validation_points": {
                "metric_selection": {
                    "acceptable_primary": ["pr_auc"],
                    "forbidden_primary": ["accuracy"],
                }
            },
            "scoring_rubric": {
                "scoping_accuracy": {"weight": 0.15, "judge": "llm"},
                "metric_selection_accuracy": {"weight": 0.10, "judge": "hybrid"},
                "temporal_leakage_detection": {"weight": 0.15, "judge": "deterministic"},
                "tool_trajectory": {"weight": 0.05, "judge": "deterministic"},
                "artifact_faithfulness": {"weight": 0.15, "judge": "llm"},
                "exec_summary_accuracy": {"weight": 0.10, "judge": "llm"},
                "approval_judgment": {"weight": 0.10, "judge": "hybrid"},
                "session_completeness": {"weight": 0.10, "judge": "hybrid"},
                "operator_satisfaction": {"weight": 0.05, "judge": "human_or_proxy"},
                "time_to_decision": {"weight": 0.05, "judge": "deterministic"},
            },
            "pass_threshold": 0.60,
            "alert_on_drop_below": 0.50,
        }
    )


@dataclass
class _ScriptedProvider:
    response_text: str
    model_id: str = "openai/gpt-4.1-mini"

    async def chat(self, messages, **kwargs):
        return LLMResponse(
            content=self.response_text,
            model=self.model_id,
            usage=Usage(input_tokens=180, output_tokens=70),
        )

    async def count_tokens(self, messages) -> int:
        return 250

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider="openai",
            display_name="Test Provider",
            max_context_tokens=128_000,
            max_output_tokens=4_096,
        )


def test_agent_eval_orchestrator_executes_agent_and_rebuilds_eval_run(tmp_path) -> None:
    provider = _ScriptedProvider(
        "Analysis complete. "
        "Core finding: premium churn remains elevated in new customers. "
        "Confidence: medium. "
        "Limitations: no retention uplift test yet. "
        "Recommended action: launch a focused retention pilot."
    )
    orchestrator = AgentEvalOrchestrator(
        workspace_dir=str(tmp_path),
        provider_factory=lambda model: provider,
        model_name=provider.model_id,
    )

    run = orchestrator.run_task(_task())

    assert run.mode == "offline"
    assert run.task_id == "retail.live_bridge.v1"
    assert run.session_id.startswith("eval-retail.live_bridge.v1-")
    assert "Core finding:" in run.final_summary
    assert run.metadata["executionBridge"] == "agent"
    assert run.metadata["requestedMode"] == "offline"
    assert run.metadata["surface"] == "eval_offline"
    assert run.metadata["runtimeStatus"] == "succeeded"
    assert run.metadata["taskStatus"] == "succeeded"
