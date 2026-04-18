from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.delivery_pack import DeliveryItem, DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.metric_spec import MetricSpec
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.task_contract import (
    Budget,
    DeliverableSpec,
    TaskContract,
    TaskContractStatus,
)
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.infrastructure.adapters.production_task_adapter import (
    ProductionTaskAdapter,
)


def test_production_task_adapter_builds_task_and_enriches_run() -> None:
    now = datetime.now(UTC)
    bundle = TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="retail_churn",
            status=TaskContractStatus.REVIEW,
            business_goal="Reduce churn among high-value subscribers.",
            budget=Budget(max_llm_cost_usd=12.0, max_wall_time_seconds=1800),
            required_deliverables=[
                DeliverableSpec(
                    type="exec_brief",
                    audience="executive",
                    format="markdown",
                ),
                DeliverableSpec(
                    type="notebook",
                    audience="ds_peer",
                    format="ipynb",
                ),
            ],
            created_at=now,
            updated_at=now,
        ),
        goal_brief=GoalBrief(
            brief_id="GB-1",
            task_id="TC-2026-001",
            business_question="Why is churn rising in premium plans?",
            ds_problem_statement="Predict churn_30d and rank intervention cohorts.",
            comparison_baseline="Current campaign heuristic",
            decision_to_make="Approve a targeted retention pilot",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        metric_specs=[
            MetricSpec(
                metric_id="MS-pr_auc",
                task_id="TC-2026-001",
                name="pr_auc",
                description="Precision recall AUC",
                formula="auc(pr_curve)",
                source_tables=["subscriptions"],
                grain="customer",
                unit="ratio",
                direction="higher_is_better",
                is_primary_kpi=True,
                created_at=now,
            )
        ],
        review_verdicts=[
            ReviewVerdict(
                verdict_id="RV-1",
                task_id="TC-2026-001",
                category="orchestrator",
                reviewer="verifier",
                summary="Narrative checks passed with one warning.",
                created_at=now,
            )
        ],
        delivery_pack=DeliveryPack(
            pack_id="DP-1",
            task_id="TC-2026-001",
            items=[
                DeliveryItem(
                    deliverable_type="exec_brief",
                    audience="executive",
                    format="markdown",
                    artifact_path="reports/exec_brief.md",
                    delivered=True,
                )
            ],
            generated_at=now,
        ),
    )
    adapter = ProductionTaskAdapter()

    task = adapter.from_bundle(bundle)
    enriched = adapter.enrich_run(
        EvalRun(
            run_id="run-1",
            session_id="session-1",
            task_id="run-1",
            mode="online",
            user_prompt="",
            started_at=1.0,
            finished_at=2.0,
        ),
        bundle,
    )

    assert task.id == "production.tc_2026_001.v1"
    assert task.prompt == "Why is churn rising in premium plans?"
    assert task.input.budget_usd == 12.0
    assert task.input.time_budget_min == 30
    assert {item.type for item in task.expected_deliverables} >= {
        "goal_brief",
        "executive_summary",
        "notebook",
    }
    assert task.validation_points.metric_selection is not None
    assert "pr_auc" in task.validation_points.metric_selection.acceptable_primary
    assert enriched.task_id == "TC-2026-001"
    assert enriched.goal_brief["business_question"] == "Why is churn rising in premium plans?"
    assert "pr_auc" in enriched.metric_choices
    assert {artifact.artifact_type for artifact in enriched.artifacts} >= {
        "goal_brief",
        "review_verdict",
        "executive_summary",
    }
