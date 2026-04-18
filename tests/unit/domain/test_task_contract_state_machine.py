from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.assumption_log import AssumptionLog
from ds_agent.domain.entities.delivery_pack import DeliveryPack
from ds_agent.domain.entities.goal_brief import GoalBrief
from ds_agent.domain.entities.review_verdict import ConfidenceBand, Issue, ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.domain.errors.task_contract_errors import DoDUnmetError, InvalidTransitionError
from ds_agent.domain.services.task_contract_state_machine import (
    TaskContractStateMachine,
    TaskContractValidator,
)


def _bundle(status: TaskContractStatus) -> TaskContractBundle:
    now = datetime(2026, 4, 15, tzinfo=UTC)
    contract = TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        status=status,
        business_goal="Reduce churn",
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        goal_brief_id="GB-1",
        assumption_log_id="AL-1",
        created_at=now,
        updated_at=now,
    )
    return TaskContractBundle(
        contract=contract,
        goal_brief=GoalBrief(
            brief_id="GB-1",
            task_id=contract.task_id,
            business_question="Why is churn rising?",
            ds_problem_statement="Binary classification",
            comparison_baseline="previous quarter",
            decision_to_make="choose top interventions",
            expected_effort="M",
            created_at=now,
            updated_at=now,
        ),
        assumption_log=AssumptionLog(log_id="AL-1", task_id=contract.task_id),
    ).sync_references()


def test_illegal_transition_rejected() -> None:
    bundle = _bundle(TaskContractStatus.DRAFT)
    with pytest.raises(InvalidTransitionError):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)


def test_in_progress_to_review_requires_verdicts() -> None:
    bundle = _bundle(TaskContractStatus.IN_PROGRESS)
    with pytest.raises(InvalidTransitionError):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)


def test_review_to_in_progress_allows_reopen() -> None:
    bundle = _bundle(TaskContractStatus.REVIEW)
    TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.IN_PROGRESS)


def test_draft_to_abandoned_allows_rejection() -> None:
    bundle = _bundle(TaskContractStatus.DRAFT)
    TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.ABANDONED)


def test_review_to_closed_requires_delivery_and_no_fails() -> None:
    bundle = _bundle(TaskContractStatus.REVIEW)
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="statistical",
            result="fail",
            reviewer="agent",
            summary="Leakage detected",
            created_at=bundle.contract.updated_at,
        )
    )
    bundle.delivery_pack = DeliveryPack(
        pack_id="DP-1",
        task_id=bundle.contract.task_id,
        items=[],
        generated_at=bundle.contract.updated_at,
    )
    with pytest.raises(DoDUnmetError):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)


def test_close_uses_latest_orchestrator_verdict_for_verifier_gates() -> None:
    bundle = _bundle(TaskContractStatus.REVIEW)
    bundle.contract.definition_of_done = {
        "criteria": ["Verifier rerun must pass before close"],
        "verifier": {
            "min_result": "warn",
            "min_confidence_grade": "medium",
            "require_no_blocking_issues": True,
        },
    }
    bundle.review_verdicts.extend(
        [
            ReviewVerdict(
                verdict_id="RV-1",
                task_id=bundle.contract.task_id,
                category="orchestrator",
                result="fail",
                reviewer="verifier",
                summary="Policy block",
                created_at=datetime(2026, 4, 15, 9, 0, tzinfo=UTC),
                blocking_issues=[Issue(message="PII policy block", layer="policy")],
                confidence=ConfidenceBand(score=0.10),
            ),
            ReviewVerdict(
                verdict_id="RV-2",
                task_id=bundle.contract.task_id,
                category="orchestrator",
                result="pass",
                reviewer="verifier",
                summary="Recovered",
                created_at=datetime(2026, 4, 15, 10, 0, tzinfo=UTC),
                confidence=ConfidenceBand(score=0.72),
            ),
        ]
    )
    bundle.delivery_pack = DeliveryPack(
        pack_id="DP-1",
        task_id=bundle.contract.task_id,
        items=[
            {
                "deliverable_type": "exec_brief",
                "audience": "executive",
                "format": "pptx",
                "artifact_path": "reports/exec.pptx",
                "delivered": True,
            }
        ],
        generated_at=bundle.contract.updated_at,
    )

    TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)
    summary = TaskContractValidator.build_dod_summary(bundle)

    assert "Latest verifier=pass | confidence=medium | blocking_issues=0" in summary
    assert "Verifier gate: result>=warn, confidence>=medium, blocking_issues=0" in summary


def test_close_rejects_missing_verifier_confidence_when_required() -> None:
    bundle = _bundle(TaskContractStatus.REVIEW)
    bundle.contract.definition_of_done = {
        "criteria": ["Verifier confidence evidence is required"],
        "verifier": {"min_confidence_grade": "medium"},
    }
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="orchestrator",
            result="warn",
            reviewer="verifier",
            summary="Manual review only",
            created_at=bundle.contract.updated_at,
        )
    )
    bundle.delivery_pack = DeliveryPack(
        pack_id="DP-1",
        task_id=bundle.contract.task_id,
        items=[
            {
                "deliverable_type": "exec_brief",
                "audience": "executive",
                "format": "pptx",
                "artifact_path": "reports/exec.pptx",
                "delivered": True,
            }
        ],
        generated_at=bundle.contract.updated_at,
    )

    with pytest.raises(DoDUnmetError, match="Verifier confidence is required"):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)
