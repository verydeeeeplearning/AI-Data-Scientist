from __future__ import annotations

from ds_agent.evaluation.application.dtos.eval_request_dto import EvalBatchRequest
from ds_agent.evaluation.application.use_cases.run_eval_batch import RunEvalBatch
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers


def _task(task_id: str) -> GoldTask:
    return GoldTask.model_validate(
        {
            "id": task_id,
            "task_version": 1,
            "domain": "retail",
            "difficulty": "easy",
            "prompt": f"Score {task_id}.",
            "input": {
                "datasets": [{"name": "x", "source": "fixtures/x.parquet"}],
                "budget_usd": 10.0,
                "time_budget_min": 20,
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
                },
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


def _run(task_id: str) -> EvalRun:
    return EvalRun.model_validate(
        {
            "run_id": f"{task_id}-run",
            "session_id": "batch-sess",
            "task_id": task_id,
            "started_at": 0,
            "finished_at": 600,
            "decision_ready_at": 500,
            "cost_usd": 1.25,
            "goal_brief": {
                "problem_framing": "Problem is scoped",
                "kpi_definition": "PR-AUC",
                "business_question": "Which users are at risk?",
                "ds_problem_statement": "Predict churn",
                "decision_to_make": "Choose a treatment cohort",
            },
            "metric_choices": ["pr_auc"],
            "tool_calls": [
                {"name": "load_data"},
                {"name": "train_model"},
                {"name": "evaluate_model"},
            ],
            "artifacts": [
                {"artifact_type": "goal_brief", "content": "complete"},
                {
                    "artifact_type": "executive_summary",
                    "content": (
                        "Core finding: pr_auc 0.81. Confidence: high. "
                        "Limitations: one cohort only. Recommended action: launch pilot."
                    ),
                },
            ],
            "underlying_metrics": {"pr_auc": 0.81},
            "final_summary": (
                "Core finding: pr_auc 0.81. Confidence: high. "
                "Limitations: one cohort only. Recommended action: launch pilot."
            ),
            "summary_sections": {
                "core_finding": "pr_auc 0.81",
                "confidence": "high",
                "limitations": "one cohort only",
                "recommended_action": "launch pilot",
            },
            "operator_feedback": {"approved_final": True},
            "metadata": {"goalStatus": "completed", "taskStatus": "succeeded"},
        }
    )


class _FakeOrchestrator:
    def __init__(self, runs: dict[str, EvalRun]) -> None:
        self._runs = runs

    def run_task(self, task: GoldTask) -> EvalRun:
        return self._runs[task.id]


class _MemoryStore:
    def __init__(self) -> None:
        self.records: list[EvalDatasetRecord] = []

    def append(self, record: EvalDatasetRecord) -> None:
        self.records.append(record)

    def load_all(self) -> list[EvalDatasetRecord]:
        return list(self.records)


def test_run_eval_batch_scores_and_persists_reports() -> None:
    tasks = (_task("retail.batch_one.v1"), _task("retail.batch_two.v1"))
    store = _MemoryStore()
    orchestrator = _FakeOrchestrator({task.id: _run(task.id) for task in tasks})

    report = RunEvalBatch(
        orchestrator=orchestrator,
        scorers=build_default_scorers(),
        eval_store=store,
    ).execute(EvalBatchRequest(tasks=tasks))

    assert report.total == 2
    assert report.passed == 2
    assert report.failed == 0
    assert len(store.records) == 2
    assert set(report.per_dimension_means) >= {"scoping_accuracy", "time_to_decision"}
    assert store.records[0].session_id == "batch-sess"
    assert store.records[0].cost_usd == 1.25
    assert store.records[0].decision_latency_seconds == 500.0
    assert "executive_summary" in store.records[0].artifact_types
    assert store.records[0].metric_choices == ("pr_auc",)
    assert store.records[0].run_metadata["goalStatus"] == "completed"
