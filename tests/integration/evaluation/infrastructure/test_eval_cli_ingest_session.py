from __future__ import annotations

from datetime import UTC, datetime

from rich.console import Console

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.domain.entities.delivery_pack import DeliveryItem, DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.domain.entities.metric_spec import MetricSpec
from ds_agent.domain.entities.task_contract import (
    Budget,
    DeliverableSpec,
    TaskContract,
)
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.evaluation.infrastructure.cli.eval_cli import run_eval_command
from ds_agent.infrastructure.persistence.task_contract_store import SqliteTaskContractStore
from ds_agent.runtime.approval_store import JsonApprovalStore
from ds_agent.runtime.organization_store import JsonOrganizationStore
from ds_agent.runtime.transcript_store import JsonTranscriptStore


def test_eval_cli_ingest_session_scores_persisted_session(tmp_path) -> None:
    workspace_dir = str(tmp_path)
    session_id = "session-456"
    run_id = "run-456"
    now = datetime.now(UTC)

    transcript_store = JsonTranscriptStore(workspace_dir=workspace_dir)
    transcript_store.replace_messages(
        session_id,
        [
            ChatMessage(role=Role.USER, content="Score the latest churn analysis."),
            ChatMessage(
                role=Role.ASSISTANT,
                content="Evaluating model",
                tool_calls=[
                    ToolCall(
                        id="tc-1",
                        name="evaluate_model",
                        arguments={"metric": "pr_auc"},
                    )
                ],
            ),
            ChatMessage(
                role=Role.TOOL,
                name="evaluate_model",
                tool_call_id="tc-1",
                content='{"metrics":{"pr_auc":0.81}}',
            ),
            ChatMessage(
                role=Role.ASSISTANT,
                content=(
                    "Core finding: premium-plan churn remains concentrated in new cohorts. "
                    "Confidence: medium. "
                    "Limitations: limited retention labels. "
                    "Recommended action: launch a pilot campaign."
                ),
            ),
        ],
    )

    approval_store = JsonApprovalStore(workspace_dir=workspace_dir)
    created = approval_store.create(
        session_id=session_id,
        run_id=run_id,
        surface="ws",
        question="Launch pilot campaign",
    )
    approval_store.resolve(created.approval_id, status=ApprovalStatus.APPROVED)

    organization_store = JsonOrganizationStore(workspace_dir=workspace_dir)
    organization_store.record_usage(
        actor_id="local-user",
        provider="anthropic",
        cost_usd=0.75,
        model="anthropic/claude-sonnet-4-6",
        session_id=session_id,
        run_id=run_id,
        recorded_at=created.created_at + 30.0,
    )

    task_store = SqliteTaskContractStore.for_workspace(workspace_dir)
    task_store.create_bundle(
        TaskContractBundle(
            contract=TaskContract(
                task_id="TC-2026-456",
                session_id=session_id,
                type="retail_churn",
                business_goal="Reduce churn in premium cohorts.",
                budget=Budget(max_llm_cost_usd=8.0, max_wall_time_seconds=1200),
                required_deliverables=[
                    DeliverableSpec(
                        type="exec_brief",
                        audience="executive",
                        format="markdown",
                    )
                ],
                created_at=now,
                updated_at=now,
            ),
            goal_brief=GoalBrief(
                brief_id="GB-456",
                task_id="TC-2026-456",
                business_question="Why is premium churn up?",
                ds_problem_statement="Predict churn_30d for premium customers.",
                comparison_baseline="Current heuristic campaign",
                decision_to_make="Approve a premium retention pilot",
                expected_effort="S",
                created_at=now,
                updated_at=now,
            ),
            metric_specs=[
                MetricSpec(
                    metric_id="MS-pr_auc",
                    task_id="TC-2026-456",
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
            delivery_pack=DeliveryPack(
                pack_id="DP-456",
                task_id="TC-2026-456",
                items=[
                    DeliveryItem(
                        deliverable_type="exec_brief",
                        audience="executive",
                        format="markdown",
                        artifact_path="reports/premium_exec.md",
                        delivered=True,
                    )
                ],
                generated_at=now,
            ),
        )
    )

    console = Console(record=True, width=140)
    exit_code = run_eval_command(
        [
            "ingest-session",
            "--session-id",
            session_id,
            "--output",
            "json",
        ],
        console=console,
        workspace_dir=workspace_dir,
    )

    output = console.export_text()
    assert exit_code == 0
    assert '"task_id": "production.tc_2026_456.v1"' in output
    assert '"weighted_score":' in output
    assert '"passed": true' in output.lower()
