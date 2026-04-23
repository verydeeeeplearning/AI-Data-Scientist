from datetime import UTC, datetime

import pytest

from ds_agent.application.services.mission_required_artifacts import (
    MissionRequiredArtifactsResolution,
)
from ds_agent.application.services.mission_required_delivery_channels import (
    MissionRequiredDeliveryChannelsResolution,
)
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


def _bundle(
    status: TaskContractStatus,
    *,
    mission: str | None = None,
    required_deliverables: list[dict[str, str]] | None = None,
) -> TaskContractBundle:
    now = datetime(2026, 4, 15, tzinfo=UTC)
    contract = TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        status=status,
        business_goal="Reduce churn",
        required_deliverables=required_deliverables
        or [{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        mission=mission,
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


def _mission_required_artifact_metadata(
    *,
    mission_name: str,
    required_artifacts: tuple[str, ...],
    mapped_required_artifacts: dict[str, tuple[str, ...]],
    unmapped_required_artifacts: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "mission_name": mission_name,
        "mission_pack_loaded": True,
        "mission_required_artifacts": list(required_artifacts),
        "mission_required_artifact_map": {
            required_artifact: list(mapped_artifacts)
            for required_artifact, mapped_artifacts in mapped_required_artifacts.items()
        },
        "mission_unmapped_required_artifacts": list(unmapped_required_artifacts),
    }


def _mission_required_check_metadata(
    *,
    mission_name: str,
    required_checks: tuple[str, ...],
    mapped_required_checks: dict[str, tuple[str, ...]],
    required_check_results: dict[str, str],
    unmapped_required_checks: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "mission_name": mission_name,
        "mission_pack_loaded": True,
        "mission_required_checks": list(required_checks),
        "mission_required_check_map": {
            required_check: list(mapped_check_ids)
            for required_check, mapped_check_ids in mapped_required_checks.items()
        },
        "mission_unmapped_required_checks": list(unmapped_required_checks),
        "mission_required_check_results": dict(required_check_results),
        "mission_required_check_failures": [
            required_check
            for required_check, status in required_check_results.items()
            if status in {"fail", "error", "missing"}
        ],
    }


def _artifact_resolution(
    *,
    mission_name: str,
    required_artifacts: tuple[str, ...],
    mapped_required_artifacts: dict[str, tuple[str, ...]],
    unmapped_required_artifacts: tuple[str, ...] = (),
    missing_contract_artifacts: tuple[str, ...] = (),
    missing_delivery_artifacts: tuple[str, ...] = (),
) -> MissionRequiredArtifactsResolution:
    return MissionRequiredArtifactsResolution(
        mission_name=mission_name,
        mission_loaded=True,
        required_artifacts=required_artifacts,
        mapped_required_artifacts=mapped_required_artifacts,
        unmapped_required_artifacts=unmapped_required_artifacts,
        missing_contract_artifacts=missing_contract_artifacts,
        missing_delivery_artifacts=missing_delivery_artifacts,
    )


def _delivery_channel_resolution(
    *,
    mission_name: str,
    required_delivery_channels: tuple[str, ...],
    mapped_required_delivery_channels: dict[str, str],
    unmapped_required_delivery_channels: tuple[str, ...] = (),
    satisfied_delivery_channels: tuple[str, ...] = (),
    missing_delivery_channels: tuple[str, ...] = (),
    dispatch_log_available: bool = True,
    delivery_pack_id: str | None = "DP-1",
) -> MissionRequiredDeliveryChannelsResolution:
    return MissionRequiredDeliveryChannelsResolution(
        mission_name=mission_name,
        mission_loaded=True,
        dispatch_log_available=dispatch_log_available,
        required_delivery_channels=required_delivery_channels,
        mapped_required_delivery_channels=mapped_required_delivery_channels,
        unmapped_required_delivery_channels=unmapped_required_delivery_channels,
        satisfied_delivery_channels=satisfied_delivery_channels,
        missing_delivery_channels=missing_delivery_channels,
        delivery_pack_id=delivery_pack_id,
    )


def _auto_verifier_review_verdict(
    *,
    task_id: str,
    summary: str,
    created_at: datetime,
    result: str = "pass",
    metadata: dict[str, object] | None = None,
) -> ReviewVerdict:
    base_metadata = {
        "source": "auto_verifier",
        "auto_verifier_mode": "shadow",
    }
    if metadata:
        base_metadata.update(metadata)
    return ReviewVerdict(
        verdict_id="RV-1",
        task_id=task_id,
        category="orchestrator",
        result=result,  # type: ignore[arg-type]
        reviewer="verifier_orchestrator",
        summary=summary,
        created_at=created_at,
        run_id="run-1",
        metadata=base_metadata,
    )


def test_illegal_transition_rejected() -> None:
    bundle = _bundle(TaskContractStatus.DRAFT)
    with pytest.raises(InvalidTransitionError):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)


def test_in_progress_to_review_requires_verdicts() -> None:
    bundle = _bundle(TaskContractStatus.IN_PROGRESS)
    with pytest.raises(InvalidTransitionError):
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)


def test_in_progress_to_review_requires_auto_verifier_verdict() -> None:
    bundle = _bundle(TaskContractStatus.IN_PROGRESS)
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="orchestrator",
            result="pass",
            reviewer="verifier",
            summary="Manual review verdict without auto verifier provenance",
            created_at=bundle.contract.updated_at,
            run_id="run-1",
        )
    )

    with pytest.raises(
        InvalidTransitionError,
        match="Latest orchestrator verdict must come from auto verifier",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)

    assert excinfo.value.metadata["kind"] == "verifier_review_gate"
    assert excinfo.value.metadata["failure"] == "latest_verdict_not_auto_verifier"


def test_in_progress_to_review_rejects_stale_auto_verifier_run_context() -> None:
    bundle = _bundle(TaskContractStatus.IN_PROGRESS)
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Auto verifier passed for an older run",
            created_at=bundle.contract.updated_at,
        )
    )

    with pytest.raises(InvalidTransitionError, match="match the active run") as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.REVIEW,
            current_run_id="run-2",
        )

    assert excinfo.value.metadata["kind"] == "verifier_review_gate"
    assert excinfo.value.metadata["failure"] == "stale_review_verdict"
    assert excinfo.value.metadata["expected_run_id"] == "run-2"
    assert excinfo.value.metadata["latest_verdict_run_id"] == "run-1"


def test_in_progress_to_review_allows_when_mission_required_artifacts_are_declared() -> None:
    bundle = _bundle(
        TaskContractStatus.IN_PROGRESS,
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Mission artifact coverage is complete",
            created_at=bundle.contract.updated_at,
            metadata=_mission_required_artifact_metadata(
                mission_name="data_analysis",
                required_artifacts=("exec_brief", "ds_appendix"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
            ),
        )
    )

    TaskContractStateMachine.validate_transition(
        bundle,
        TaskContractStatus.REVIEW,
        mission_artifact_resolution=_artifact_resolution(
            mission_name="data_analysis",
            required_artifacts=("exec_brief", "ds_appendix"),
            mapped_required_artifacts={
                "exec_brief": ("exec_brief",),
                "ds_appendix": ("ds_appendix",),
            },
        ),
    )


def test_in_progress_to_review_rejects_unmapped_mission_required_artifacts() -> None:
    bundle = _bundle(
        TaskContractStatus.IN_PROGRESS,
        mission="custom-mission",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Mission artifact coverage is incomplete",
            created_at=bundle.contract.updated_at,
            metadata=_mission_required_artifact_metadata(
                mission_name="custom-mission",
                required_artifacts=("exec_brief", "ds_appendix", "sql_notes"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
                unmapped_required_artifacts=("sql_notes",),
            ),
        )
    )

    with pytest.raises(
        InvalidTransitionError,
        match=r"(?i)not mapped.*sql_notes",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.REVIEW,
            mission_artifact_resolution=_artifact_resolution(
                mission_name="custom-mission",
                required_artifacts=("exec_brief", "ds_appendix", "sql_notes"),
                mapped_required_artifacts={
                    "exec_brief": ("exec_brief",),
                    "ds_appendix": ("ds_appendix",),
                },
                unmapped_required_artifacts=("sql_notes",),
            ),
        )
    assert excinfo.value.metadata == {
        "kind": "mission_artifact_gate",
        "transition_target": "review",
        "failure": "unmapped_required_artifacts",
        "mission_name": "custom-mission",
        "mission_loaded": True,
        "required_artifacts": ["exec_brief", "ds_appendix", "sql_notes"],
        "mapped_required_artifacts": {
            "exec_brief": ["exec_brief"],
            "ds_appendix": ["ds_appendix"],
        },
        "unmapped_required_artifacts": ["sql_notes"],
        "missing_contract_artifacts": [],
        "missing_delivery_artifacts": [],
    }


def test_in_progress_to_review_rejects_failed_mission_required_checks() -> None:
    bundle = _bundle(
        TaskContractStatus.IN_PROGRESS,
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Baseline check failed for the mission",
            created_at=bundle.contract.updated_at,
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
            ),
        )
    )

    with pytest.raises(
        InvalidTransitionError,
        match=r"(?i)must pass.*baseline_compare",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)

    assert excinfo.value.metadata == {
        "kind": "mission_check_gate",
        "transition_target": "review",
        "failure": "failed_required_checks",
        "mission_name": "data_analysis",
        "mission_loaded": True,
        "required_checks": [
            "schema_drift",
            "metric_definition_confirmed",
            "subgroup_stability",
            "baseline_compare",
        ],
        "mapped_required_checks": {
            "schema_drift": ["schema_contract_validation"],
            "metric_definition_confirmed": ["metric_definition_confirmed"],
            "subgroup_stability": ["subgroup_stability"],
            "baseline_compare": ["baseline_comparison"],
        },
        "unmapped_required_checks": [],
        "required_check_results": {
            "schema_drift": "pass",
            "metric_definition_confirmed": "pass",
            "subgroup_stability": "pass",
            "baseline_compare": "fail",
        },
        "required_check_failures": ["baseline_compare"],
    }


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


def test_build_dod_summary_surfaces_mission_artifact_gate_status() -> None:
    bundle = _bundle(
        TaskContractStatus.REVIEW,
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="orchestrator",
            result="pass",
            reviewer="verifier",
            summary="Ready for close",
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

    summary = TaskContractValidator.build_dod_summary(
        bundle,
        mission_artifact_resolution=_artifact_resolution(
            mission_name="data_analysis",
            required_artifacts=("exec_brief", "ds_appendix"),
            mapped_required_artifacts={
                "exec_brief": ("exec_brief",),
                "ds_appendix": ("ds_appendix",),
            },
            missing_delivery_artifacts=("ds_appendix",),
        ),
    )

    assert "Mission artifacts [data_analysis]: required=exec_brief, ds_appendix" in summary
    assert "Mission artifacts gate: delivery_missing=ds_appendix" in summary


def test_build_dod_summary_surfaces_mission_check_gate_status() -> None:
    bundle = _bundle(
        TaskContractStatus.REVIEW,
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Baseline check still failing",
            created_at=bundle.contract.updated_at,
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
            ),
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
            },
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
        ],
        generated_at=bundle.contract.updated_at,
    )

    summary = TaskContractValidator.build_dod_summary(bundle)

    assert (
        "Mission checks [data_analysis]: required="
        "schema_drift, metric_definition_confirmed, subgroup_stability, baseline_compare"
    ) in summary
    assert "Mission checks gate: failed=baseline_compare" in summary


def test_build_dod_summary_surfaces_mission_delivery_channel_gate_status() -> None:
    bundle = _bundle(
        TaskContractStatus.REVIEW,
        mission="weekly-kpi-triage",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="orchestrator",
            result="pass",
            reviewer="verifier",
            summary="Ready for close",
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
            },
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
        ],
        generated_at=bundle.contract.updated_at,
    )

    summary = TaskContractValidator.build_dod_summary(
        bundle,
        mission_delivery_channel_resolution=_delivery_channel_resolution(
            mission_name="weekly-kpi-triage",
            required_delivery_channels=("jira_ticket",),
            mapped_required_delivery_channels={"jira_ticket": "jira_ticket"},
            missing_delivery_channels=("jira_ticket",),
        ),
    )

    assert "Mission delivery channels [weekly-kpi-triage]: required=jira_ticket" in summary
    assert "Mission delivery channels gate: delivery_missing=jira_ticket" in summary


def test_close_rejects_failed_mission_required_checks() -> None:
    bundle = _bundle(
        TaskContractStatus.REVIEW,
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        _auto_verifier_review_verdict(
            task_id=bundle.contract.task_id,
            summary="Baseline check still failing",
            created_at=bundle.contract.updated_at,
            metadata=_mission_required_check_metadata(
                mission_name="data_analysis",
                required_checks=(
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ),
                mapped_required_checks={
                    "schema_drift": ("schema_contract_validation",),
                    "metric_definition_confirmed": ("metric_definition_confirmed",),
                    "subgroup_stability": ("subgroup_stability",),
                    "baseline_compare": ("baseline_comparison",),
                },
                required_check_results={
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
            ),
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
            },
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
        ],
        generated_at=bundle.contract.updated_at,
    )

    with pytest.raises(
        DoDUnmetError,
        match=r"(?i)must pass.*baseline_compare",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)

    assert excinfo.value.metadata == {
        "kind": "mission_check_gate",
        "transition_target": "close",
        "failure": "failed_required_checks",
        "mission_name": "data_analysis",
        "mission_loaded": True,
        "required_checks": [
            "schema_drift",
            "metric_definition_confirmed",
            "subgroup_stability",
            "baseline_compare",
        ],
        "mapped_required_checks": {
            "schema_drift": ["schema_contract_validation"],
            "metric_definition_confirmed": ["metric_definition_confirmed"],
            "subgroup_stability": ["subgroup_stability"],
            "baseline_compare": ["baseline_comparison"],
        },
        "unmapped_required_checks": [],
        "required_check_results": {
            "schema_drift": "pass",
            "metric_definition_confirmed": "pass",
            "subgroup_stability": "pass",
            "baseline_compare": "fail",
        },
        "required_check_failures": ["baseline_compare"],
    }


def test_close_rejects_missing_mission_required_delivery_channel() -> None:
    bundle = _bundle(
        TaskContractStatus.REVIEW,
        mission="weekly-kpi-triage",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        ReviewVerdict(
            verdict_id="RV-1",
            task_id=bundle.contract.task_id,
            category="orchestrator",
            result="pass",
            reviewer="verifier",
            summary="Ready for close",
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
            },
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
        ],
        generated_at=bundle.contract.updated_at,
    )

    with pytest.raises(
        DoDUnmetError,
        match=r"(?i)persisted dispatch records: jira_ticket",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.CLOSED,
            mission_delivery_channel_resolution=_delivery_channel_resolution(
                mission_name="weekly-kpi-triage",
                required_delivery_channels=("jira_ticket",),
                mapped_required_delivery_channels={"jira_ticket": "jira_ticket"},
                missing_delivery_channels=("jira_ticket",),
            ),
        )

    assert excinfo.value.metadata == {
        "kind": "mission_delivery_channel_gate",
        "transition_target": "close",
        "failure": "missing_delivery_channels",
        "mission_name": "weekly-kpi-triage",
        "mission_loaded": True,
        "dispatch_log_available": True,
        "required_delivery_channels": ["jira_ticket"],
        "mapped_required_delivery_channels": {"jira_ticket": "jira_ticket"},
        "unmapped_required_delivery_channels": [],
        "satisfied_delivery_channels": [],
        "missing_delivery_channels": ["jira_ticket"],
        "delivery_pack_id": "DP-1",
    }


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
