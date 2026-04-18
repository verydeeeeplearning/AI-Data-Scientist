"""Adapters that map production task contracts into eval tasks."""

from __future__ import annotations

import json
import re
from math import ceil

from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.evaluation.domain.entities.eval_run import EvalArtifact, EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask

_DELIVERABLE_TYPE_MAP = {
    "exec_brief": "executive_summary",
    "ds_appendix": "eda_report",
    "action_proposals": "action_proposals",
    "dashboard": "dashboard",
    "notebook": "notebook",
    "email": "stakeholder_message",
    "slack_thread": "stakeholder_message",
}


class ProductionTaskAdapter:
    """Create synthetic eval tasks and enrich runs from task contracts."""

    def from_bundle(self, bundle: TaskContractBundle) -> GoldTask:
        contract = bundle.contract
        budget = contract.budget
        budget_usd = (
            budget.max_llm_cost_usd
            or budget.max_compute_cost_usd
            or 0.0
        )
        time_budget_min = (
            0
            if budget.max_wall_time_seconds is None
            else ceil(budget.max_wall_time_seconds / 60.0)
        )
        deliverables: list[dict[str, object]] = []
        if bundle.goal_brief is not None:
            deliverables.append(
                {
                    "type": "goal_brief",
                    "must_contain": [
                        "business_question",
                        "ds_problem_statement",
                        "decision_to_make",
                        "comparison_baseline",
                    ],
                }
            )
        for item in contract.required_deliverables:
            mapped_type = _DELIVERABLE_TYPE_MAP.get(item.type, item.type)
            deliverables.append({"type": mapped_type})
        if not any(item["type"] == "executive_summary" for item in deliverables):
            deliverables.append({"type": "executive_summary"})

        metric_names = [metric.name for metric in bundle.metric_specs]
        return GoldTask.model_validate(
            {
                "id": f"production.{_safe_fragment(contract.task_id)}.v1",
                "task_version": 1,
                "domain": _safe_fragment(contract.type or "generic"),
                "difficulty": "medium",
                "tags": sorted(
                    {
                        contract.type,
                        *(item.type for item in contract.required_deliverables),
                    }
                ),
                "prompt": (
                    bundle.goal_brief.business_question
                    if bundle.goal_brief is not None
                    else contract.business_goal
                ),
                "input": {
                    "budget_usd": budget_usd,
                    "time_budget_min": time_budget_min,
                },
                "expected_deliverables": deliverables,
                "validation_points": {
                    "metric_selection": {
                        "acceptable_primary": metric_names,
                        "forbidden_primary": [],
                    },
                    "approval_required": {},
                },
                "baseline": {},
                "scoring_rubric": _default_scoring_rubric(),
                "pass_threshold": 0.65,
                "alert_on_drop_below": 0.60,
            }
        )

    def from_session(
        self,
        *,
        session_id: str,
        prompt: str,
        task_id: str | None = None,
    ) -> GoldTask:
        resolved_task = task_id or session_id
        return GoldTask.model_validate(
            {
                "id": f"production.{_safe_fragment(resolved_task)}.v1",
                "task_version": 1,
                "domain": "generic",
                "difficulty": "medium",
                "tags": ["production", "session"],
                "prompt": prompt.strip() or f"Evaluate production session {session_id}.",
                "input": {
                    "budget_usd": 0.0,
                    "time_budget_min": 0,
                },
                "expected_deliverables": [
                    {"type": "executive_summary"},
                ],
                "validation_points": {
                    "metric_selection": {
                        "acceptable_primary": [],
                        "forbidden_primary": [],
                    },
                    "approval_required": {},
                },
                "baseline": {},
                "scoring_rubric": _default_scoring_rubric(),
                "pass_threshold": 0.60,
                "alert_on_drop_below": 0.55,
            }
        )

    def enrich_run(self, run: EvalRun, bundle: TaskContractBundle) -> EvalRun:
        goal_brief = dict(run.goal_brief)
        artifacts = list(run.artifacts)
        metric_choices = list(run.metric_choices)

        if bundle.goal_brief is not None:
            goal_brief.update(
                {
                    "business_question": bundle.goal_brief.business_question,
                    "ds_problem_statement": bundle.goal_brief.ds_problem_statement,
                    "decision_to_make": bundle.goal_brief.decision_to_make,
                    "comparison_baseline": bundle.goal_brief.comparison_baseline,
                }
            )
            artifacts.append(
                EvalArtifact(
                    artifact_type="goal_brief",
                    content=json.dumps(goal_brief, ensure_ascii=False),
                    evidence_refs=(bundle.goal_brief.brief_id,),
                )
            )

        for metric in bundle.metric_specs:
            if metric.name not in metric_choices:
                metric_choices.append(metric.name)

        for verdict in bundle.review_verdicts:
            artifacts.append(
                EvalArtifact(
                    artifact_type="review_verdict",
                    content=verdict.summary or "",
                    evidence_refs=tuple(verdict.evidence_refs) or (verdict.verdict_id,),
                    metadata={"result": verdict.result},
                )
            )

        if bundle.delivery_pack is not None:
            for item in bundle.delivery_pack.items:
                artifacts.append(
                    EvalArtifact(
                        artifact_type=_DELIVERABLE_TYPE_MAP.get(
                            item.deliverable_type,
                            item.deliverable_type,
                        ),
                        content=item.artifact_path,
                        evidence_refs=(item.artifact_path,),
                        metadata={
                            "audience": item.audience,
                            "format": item.format,
                            "delivered": item.delivered,
                        },
                    )
                )

        return run.model_copy(
            update={
                "task_id": bundle.contract.task_id,
                "user_prompt": run.user_prompt or bundle.contract.business_goal,
                "goal_brief": goal_brief,
                "metric_choices": tuple(metric_choices),
                "artifacts": tuple(artifacts),
            }
        )


def _safe_fragment(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "session"


def _default_scoring_rubric() -> dict[str, dict[str, object]]:
    return {
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
    }

