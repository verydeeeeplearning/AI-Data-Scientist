from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord, EvalScore
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.cli import eval_cli
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.evaluation.infrastructure.persistence.jsonl_eval_dataset_store import (
    JsonlEvalDatasetStore,
)
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore


def test_eval_cli_run_with_candidate_promotes_pending_skill(tmp_path: Path, monkeypatch) -> None:
    tasks_dir = tmp_path / "gold"
    runs_dir = tmp_path / "runs"
    custom_dir = tmp_path / "custom"
    tasks_dir.mkdir()
    runs_dir.mkdir()
    custom_dir.mkdir()

    monkeypatch.setattr(eval_cli, "_default_active_custom_skills_dir", lambda: custom_dir)

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

    JsonlEvalDatasetStore.for_workspace(str(tmp_path)).append(
        EvalDatasetRecord(
            task_id="retail.live_bridge.v1",
            run_id="baseline-run",
            mode="offline",
            weighted_score=0.50,
            passed=True,
            scores={
                "scoping_accuracy": EvalScore(
                    name="scoping_accuracy",
                    value=0.50,
                    rationale="baseline",
                    judge_type=JudgeType.LLM,
                )
            },
            run_metadata={"taskDomain": "retail"},
        )
    )

    candidate_store = JsonPromotionCandidateStore.for_workspace(str(tmp_path))
    pending_dir = candidate_store.path.parent / "pending_skills"
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending_path = pending_dir / "candidate-skill.md"
    pending_path.write_text(
        "---\n"
        "name: candidate-skill\n"
        "description: pending skill\n"
        "category: extracted\n"
        'tags: ["extracted"]\n'
        "---\n\n# Candidate Skill\n",
        encoding="utf-8",
    )
    candidate = candidate_store.register_skill_candidate(
        candidate_id="candidate-001",
        name="candidate-skill",
        description="pending skill",
        source_project_id="proj-001",
        pending_path=pending_path,
    )

    console = Console(record=True, width=140)
    exit_code = run_eval_command(
        [
            "run",
            "--tasks-dir",
            str(tasks_dir),
            "--runs-dir",
            str(runs_dir),
            "--with-candidate",
            candidate.candidate_id,
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=str(tmp_path),
    )

    output = console.export_text()
    promoted = candidate_store.get(candidate.candidate_id)
    assert exit_code == 0
    assert '"candidatePromotion"' in output
    assert promoted is not None
    assert promoted.status == "promoted"
    assert promoted.promoted_path is not None
    assert Path(promoted.promoted_path).exists()
