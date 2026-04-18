from __future__ import annotations

from ds_agent.evaluation.application.use_cases.run_shadow_comparison import (
    RunShadowComparison,
)
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers


def _task(task_id: str = "production.shadow_compare.v1") -> GoldTask:
    return GoldTask.model_validate(
        {
            "id": task_id,
            "task_version": 1,
            "domain": "retail",
            "difficulty": "easy",
            "prompt": "Compare premium churn triage quality.",
            "input": {
                "datasets": [{"name": "premium_customers", "source": "fixtures/premium.csv"}],
                "budget_usd": 8.0,
                "time_budget_min": 20,
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
        }
    )


def _run(
    *,
    run_id: str,
    session_id: str,
    mode: str,
    decision_ready_at: float,
    model: str,
) -> EvalRun:
    return EvalRun.model_validate(
        {
            "run_id": run_id,
            "session_id": session_id,
            "task_id": "production.shadow_compare.v1",
            "mode": mode,
            "user_prompt": "Compare premium churn triage quality.",
            "started_at": 0,
            "finished_at": 600,
            "decision_ready_at": decision_ready_at,
            "cost_usd": 0.75,
            "metric_choices": ["pr_auc"],
            "tool_calls": [
                {"name": "load_data"},
                {"name": "evaluate_model"},
            ],
            "artifacts": [
                {
                    "artifact_type": "executive_summary",
                    "content": (
                        "Core finding: churn concentrates in new premium cohorts. "
                        "Confidence: medium. "
                        "Limitations: limited retention labels. "
                        "Recommended action: launch a retention pilot."
                    ),
                }
            ],
            "underlying_metrics": {"pr_auc": 0.81},
            "final_summary": (
                "Core finding: churn concentrates in new premium cohorts. "
                "Confidence: medium. "
                "Limitations: limited retention labels. "
                "Recommended action: launch a retention pilot."
            ),
            "summary_sections": {
                "core_finding": "churn concentrates in new premium cohorts",
                "confidence": "medium",
                "limitations": "limited retention labels",
                "recommended_action": "launch a retention pilot",
            },
            "metadata": {
                "goalStatus": "completed",
                "taskStatus": "succeeded",
                "model": model,
            },
        }
    )


class _FakeTraceReader:
    def __init__(self, run: EvalRun) -> None:
        self._run = run

    def read_session(
        self,
        *,
        session_id: str,
        task_id: str | None = None,
        run_id: str | None = None,
    ):
        return self._run


class _FakeOrchestrator:
    def __init__(self, shadow_run: EvalRun) -> None:
        self._shadow_run = shadow_run

    def run_task(self, task: GoldTask) -> EvalRun:
        return self._shadow_run


class _MemoryComparisonStore:
    def __init__(self) -> None:
        self.records: list[ShadowComparisonRecord] = []

    def append(self, record: ShadowComparisonRecord) -> None:
        self.records.append(record)

    def latest_for_baseline_run(self, baseline_run_id: str) -> ShadowComparisonRecord | None:
        matches = [record for record in self.records if record.baseline_run_id == baseline_run_id]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)


class _MemoryEvalStore:
    def __init__(self) -> None:
        self.records: list[EvalDatasetRecord] = []

    def append(self, record: EvalDatasetRecord) -> None:
        self.records.append(record)

    def load_all(self) -> list[EvalDatasetRecord]:
        return list(self.records)


def test_run_shadow_comparison_scores_both_paths_and_persists_comparison() -> None:
    baseline_run = _run(
        run_id="baseline-run",
        session_id="session-1",
        mode="online",
        decision_ready_at=420,
        model="anthropic/claude-sonnet-4-6",
    )
    shadow_run = _run(
        run_id="shadow-run",
        session_id="eval-shadow-session",
        mode="shadow",
        decision_ready_at=120,
        model="openai/gpt-4.1-mini",
    )
    comparison_store = _MemoryComparisonStore()
    eval_store = _MemoryEvalStore()

    record = RunShadowComparison(
        trace_reader=_FakeTraceReader(baseline_run),
        shadow_orchestrator=_FakeOrchestrator(shadow_run),
        scorers=build_default_scorers(),
        comparison_store=comparison_store,
        eval_store=eval_store,
        shadow_model="openai/gpt-4.1-mini",
        shadow_budget_factor=0.5,
    ).execute(
        session_id="session-1",
        task=_task(),
        baseline_run=baseline_run,
    )

    assert record.session_id == "session-1"
    assert record.baseline_run_id == "baseline-run"
    assert record.shadow_run_id == "shadow-run"
    assert record.shadow_model == "openai/gpt-4.1-mini"
    assert comparison_store.latest_for_baseline_run("baseline-run") == record
    assert len(record.dimension_deltas) > 0
    assert len(eval_store.records) == 2
    assert eval_store.records[0].run_metadata["shadowComparisonId"] == record.comparison_id
    assert eval_store.records[0].run_metadata["shadowRole"] == "baseline"
    assert eval_store.records[1].mode == "shadow"
    assert eval_store.records[1].run_metadata["shadowRole"] == "shadow"
