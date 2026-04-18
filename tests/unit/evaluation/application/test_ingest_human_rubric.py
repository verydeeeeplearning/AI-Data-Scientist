from __future__ import annotations

from ds_agent.evaluation.application.use_cases.ingest_human_rubric import IngestHumanRubric
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric, HumanRubricRecord
from ds_agent.evaluation.infrastructure.scorers.registry import build_default_scorers


def _task() -> GoldTask:
    return GoldTask.model_validate(
        {
            "id": "production.retail.v1",
            "task_version": 1,
            "domain": "retail",
            "difficulty": "easy",
            "prompt": "Evaluate premium churn risk.",
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
        }
    )


def _run() -> EvalRun:
    return EvalRun.model_validate(
        {
            "run_id": "run-1",
            "session_id": "session-1",
            "task_id": "production.retail.v1",
            "mode": "online",
            "started_at": 0,
            "finished_at": 120,
            "decision_ready_at": 90,
            "cost_usd": 0.4,
            "metric_choices": ["pr_auc"],
            "goal_brief": {
                "problem_framing": "scope complete",
                "kpi_definition": "use pr_auc",
            },
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
    )


class _TraceReader:
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


class _RubricStore:
    def __init__(self) -> None:
        self.records: list[HumanRubricRecord] = []

    def append(self, record: HumanRubricRecord) -> None:
        self.records.append(record)

    def latest(self, *, session_id: str, run_id: str | None = None) -> HumanRubricRecord | None:
        return None


def test_ingest_human_rubric_persists_and_overrides_scores() -> None:
    store = _RubricStore()
    rubric = HumanRubric(
        reviewer_id="reviewer-1",
        dimensions={
            "scoping_accuracy": 0.25,
            "operator_satisfaction": 0.95,
        },
        comment="Scope framing was weak but the operator experience was excellent.",
    )

    report = IngestHumanRubric(
        trace_reader=_TraceReader(_run()),
        rubric_store=store,
        scorers=build_default_scorers(),
    ).execute(
        session_id="session-1",
        rubric=rubric,
        task=_task(),
    )

    assert len(store.records) == 1
    assert store.records[0].rubric.reviewer_id == "reviewer-1"
    assert report.scores["scoping_accuracy"].value == 0.25
    assert report.scores["operator_satisfaction"].value == 0.95
    assert report.scores["scoping_accuracy"].sub_scores["auto_score"] > 0.25
