from __future__ import annotations

from dataclasses import dataclass

import yaml
from rich.console import Console

from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command


@dataclass
class _ScriptedProvider:
    response_text: str
    model_id: str = "openai/gpt-4.1-mini"

    async def chat(self, messages, **kwargs):
        return LLMResponse(
            content=self.response_text,
            model=self.model_id,
            usage=Usage(input_tokens=120, output_tokens=60),
        )

    async def count_tokens(self, messages) -> int:
        return 180

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider="openai",
            display_name="CLI Test Provider",
            max_context_tokens=128_000,
            max_output_tokens=4_096,
        )


def test_eval_cli_run_supports_agent_runner(tmp_path) -> None:
    tasks_dir = tmp_path / "gold"
    tasks_dir.mkdir()
    (tasks_dir / "retail.live_bridge.v1.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "retail.live_bridge.v1",
                "task_version": 1,
                "domain": "retail",
                "difficulty": "easy",
                "prompt": "Assess premium churn risk and decide the next action.",
                "input": {
                    "datasets": [
                        {"name": "premium_customers", "source": "fixtures/premium.csv"}
                    ],
                    "budget_usd": 5.0,
                    "time_budget_min": 15,
                },
                "expected_deliverables": [{"type": "executive_summary"}],
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
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    provider = _ScriptedProvider(
        "Analysis complete. "
        "Core finding: churn is concentrated in the newest premium cohort. "
        "Confidence: medium. "
        "Limitations: no retention experiment yet. "
        "Recommended action: launch a premium save offer pilot."
    )
    console = Console(record=True, width=140)

    exit_code = run_eval_command(
        [
            "run",
            "--tasks-dir",
            str(tasks_dir),
            "--runner",
            "agent",
            "--model",
            provider.model_id,
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=str(tmp_path),
        provider_factory=lambda model: provider,
        default_model=provider.model_id,
    )

    output = console.export_text()
    assert exit_code == 0
    assert '"total": 1' in output
    assert '"retail.live_bridge.v1"' in output


def test_eval_cli_run_keeps_directory_runner_path(tmp_path) -> None:
    tasks_dir = tmp_path / "gold"
    runs_dir = tmp_path / "runs"
    tasks_dir.mkdir()
    runs_dir.mkdir()
    (tasks_dir / "retail.live_bridge.v1.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "retail.live_bridge.v1",
                "task_version": 1,
                "domain": "retail",
                "difficulty": "easy",
                "prompt": "Assess premium churn risk and decide the next action.",
                "input": {"datasets": [], "budget_usd": 5.0, "time_budget_min": 15},
                "expected_deliverables": [{"type": "executive_summary"}],
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
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (runs_dir / "retail.live_bridge.v1.json").write_text(
        EvalRun.model_validate(
            {
                "run_id": "fixture-run",
                "session_id": "fixture-session",
                "task_id": "retail.live_bridge.v1",
                "started_at": 0,
                "finished_at": 120,
                "decision_ready_at": 90,
                "cost_usd": 0.4,
                "metric_choices": ["pr_auc"],
                "artifacts": [
                    {
                        "artifact_type": "executive_summary",
                        "content": (
                            "Core finding: churn concentrates in new premium cohorts. "
                            "Confidence: medium. "
                            "Limitations: short observation window. "
                            "Recommended action: launch a pilot."
                        ),
                    }
                ],
                "final_summary": (
                    "Core finding: churn concentrates in new premium cohorts. "
                    "Confidence: medium. "
                    "Limitations: short observation window. "
                    "Recommended action: launch a pilot."
                ),
                "summary_sections": {
                    "core_finding": "churn concentrates in new premium cohorts.",
                    "confidence": "medium.",
                    "limitations": "short observation window.",
                    "recommended_action": "launch a pilot.",
                },
                "metadata": {"goalStatus": "completed", "taskStatus": "succeeded"},
            }
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    console = Console(record=True, width=140)

    exit_code = run_eval_command(
        [
            "run",
            "--tasks-dir",
            str(tasks_dir),
            "--runs-dir",
            str(runs_dir),
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=str(tmp_path),
    )

    output = console.export_text()
    assert exit_code == 0
    assert '"total": 1' in output
    assert '"retail.live_bridge.v1"' in output
