from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.application.services.mission_required_artifacts import (
    MissionRequiredArtifactResolver,
)
from ds_agent.application.services.mission_required_delivery_channels import (
    MissionRequiredDeliveryChannelResolver,
)
from ds_agent.domain.entities.delivery_pack import DeliveryChannel
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.domain.errors.task_contract_errors import DoDUnmetError, InvalidTransitionError
from ds_agent.domain.services.task_contract_state_machine import (
    TaskContractStateMachine,
    TaskContractValidator,
)

pytestmark = pytest.mark.contract


def test_review_contract_requires_auto_verifier_provenance(
    make_contract_bundle,
    make_review_verdict,
) -> None:
    bundle = make_contract_bundle(status=TaskContractStatus.IN_PROGRESS)
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-2026010",
            result="pass",
            summary="Manual verdict exists but not from the auto verifier",
        )
    )

    with pytest.raises(InvalidTransitionError, match="auto verifier") as excinfo:
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)

    assert excinfo.value.metadata["kind"] == "verifier_review_gate"
    assert excinfo.value.metadata["failure"] == "latest_verdict_not_auto_verifier"


def test_review_contract_requires_fresh_auto_verifier_run_context(
    make_contract_bundle,
    make_review_verdict,
) -> None:
    bundle = make_contract_bundle(status=TaskContractStatus.IN_PROGRESS)
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-20260101",
            result="pass",
            summary="Auto verifier passed for a previous run",
            reviewer="verifier_orchestrator",
            run_id="run-auto-1",
            metadata={"source": "auto_verifier"},
        )
    )

    with pytest.raises(InvalidTransitionError, match="active run") as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.REVIEW,
            current_run_id="run-auto-2",
        )

    assert excinfo.value.metadata["kind"] == "verifier_review_gate"
    assert excinfo.value.metadata["failure"] == "stale_review_verdict"
    assert excinfo.value.metadata["expected_run_id"] == "run-auto-2"
    assert excinfo.value.metadata["latest_verdict_run_id"] == "run-auto-1"


def test_data_analysis_review_contract_rejects_failed_mission_required_checks(
    make_contract_bundle,
    make_review_verdict,
) -> None:
    bundle = make_contract_bundle(
        mission="data_analysis",
        status=TaskContractStatus.IN_PROGRESS,
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-20260101",
            result="pass",
            summary="Baseline comparison failed for the active mission",
            run_id="run-auto-1",
            metadata={
                "source": "auto_verifier",
                "mission_name": "data_analysis",
                "mission_pack_loaded": True,
                "mission_required_checks": [
                    "schema_drift",
                    "metric_definition_confirmed",
                    "subgroup_stability",
                    "baseline_compare",
                ],
                "mission_required_check_map": {
                    "schema_drift": ["schema_contract_validation"],
                    "metric_definition_confirmed": ["metric_definition_confirmed"],
                    "subgroup_stability": ["subgroup_stability"],
                    "baseline_compare": ["baseline_comparison"],
                },
                "mission_unmapped_required_checks": [],
                "mission_required_check_results": {
                    "schema_drift": "pass",
                    "metric_definition_confirmed": "pass",
                    "subgroup_stability": "pass",
                    "baseline_compare": "fail",
                },
                "mission_required_check_failures": ["baseline_compare"],
            },
        )
    )

    with pytest.raises(
        InvalidTransitionError,
        match="baseline_compare",
    ) as excinfo:
        TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.REVIEW)

    assert excinfo.value.metadata["kind"] == "mission_check_gate"
    assert excinfo.value.metadata["failure"] == "failed_required_checks"
    assert excinfo.value.metadata["required_check_failures"] == ["baseline_compare"]


def test_weekly_kpi_triage_review_contract_requires_declared_ds_appendix(
    mission_loader,
    make_contract_bundle,
    make_review_verdict,
) -> None:
    bundle = make_contract_bundle(
        mission="weekly-kpi-triage",
        status=TaskContractStatus.IN_PROGRESS,
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
        ],
    )
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-2026011",
            result="pass",
            summary="Verifier passed for review entry",
            run_id="run-auto-1",
            metadata={"source": "auto_verifier"},
        )
    )
    resolution = MissionRequiredArtifactResolver(mission_loader).resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.required_artifacts == ("exec_brief", "ds_appendix")
    assert resolution.missing_contract_artifacts == ("ds_appendix",)

    with pytest.raises(InvalidTransitionError, match="required_deliverables") as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.REVIEW,
            mission_artifact_resolution=resolution,
        )

    assert excinfo.value.metadata["kind"] == "mission_artifact_gate"
    assert excinfo.value.metadata["failure"] == "missing_contract_artifacts"
    assert excinfo.value.metadata["missing_contract_artifacts"] == ["ds_appendix"]


def test_weekly_kpi_triage_close_contract_requires_jira_dispatch_evidence(
    mission_loader,
    dispatch_log_reader_factory,
    make_contract_bundle,
    make_review_verdict,
    make_delivery_pack,
) -> None:
    bundle = make_contract_bundle(
        mission="weekly-kpi-triage",
        status=TaskContractStatus.REVIEW,
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-2026021",
            result="pass",
            summary="Verifier passed for close",
        )
    )
    bundle.delivery_pack = make_delivery_pack(
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
    )
    resolution = MissionRequiredDeliveryChannelResolver(
        mission_loader,
        dispatch_log_reader_factory(records=()),
    ).resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.required_delivery_channels == ("jira_ticket",)
    assert resolution.missing_delivery_channels == ("jira_ticket",)

    with pytest.raises(DoDUnmetError, match="dispatch records") as excinfo:
        TaskContractStateMachine.validate_transition(
            bundle,
            TaskContractStatus.CLOSED,
            mission_delivery_channel_resolution=resolution,
        )

    assert excinfo.value.metadata["kind"] == "mission_delivery_channel_gate"
    assert excinfo.value.metadata["failure"] == "missing_delivery_channels"
    assert excinfo.value.metadata["missing_delivery_channels"] == ["jira_ticket"]


def test_weekly_kpi_triage_close_contract_accepts_persisted_jira_dispatch(
    mission_loader,
    dispatch_log_reader_factory,
    make_contract_bundle,
    make_review_verdict,
    make_delivery_pack,
    make_dispatch_record,
) -> None:
    bundle = make_contract_bundle(
        mission="weekly-kpi-triage",
        status=TaskContractStatus.REVIEW,
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )
    bundle.review_verdicts.append(
        make_review_verdict(
            task_id=bundle.contract.task_id,
            verdict_id="RV-2026022",
            result="pass",
            summary="Verifier passed for close",
        )
    )
    bundle.delivery_pack = make_delivery_pack(
        task_id=bundle.contract.task_id,
        items=[
            {
                "deliverable_type": "exec_brief",
                "audience": "executive",
                "format": "pptx",
                "artifact_path": "reports/exec.pptx",
                "delivered": True,
                "artifact_id": "artifact-exec",
            },
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
                "artifact_id": "artifact-appendix",
            },
        ],
    )
    dispatch_reader = dispatch_log_reader_factory(
        records=(
            make_dispatch_record(
                task_id=bundle.contract.task_id,
                pack_id=bundle.delivery_pack.pack_id,
                artifact_id="artifact-exec",
                channel=DeliveryChannel.JIRA_TICKET,
            ),
        )
    )
    resolution = MissionRequiredDeliveryChannelResolver(
        mission_loader,
        dispatch_reader,
    ).resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.satisfied_delivery_channels == ("jira_ticket",)

    TaskContractStateMachine.validate_transition(
        bundle,
        TaskContractStatus.CLOSED,
        mission_delivery_channel_resolution=resolution,
    )


def test_close_contract_uses_latest_orchestrator_verdict_as_authority(
    make_contract_bundle,
    make_review_verdict,
    make_delivery_pack,
) -> None:
    bundle = make_contract_bundle(
        status=TaskContractStatus.REVIEW,
        definition_of_done={
            "criteria": ["Latest orchestrator verdict must stay above warning"],
            "verifier": {
                "min_result": "warn",
                "min_confidence_grade": "medium",
                "require_no_blocking_issues": True,
            },
        },
    )
    bundle.review_verdicts.extend(
        [
            make_review_verdict(
                task_id=bundle.contract.task_id,
                verdict_id="RV-2026031",
                category="orchestrator",
                result="pass",
                summary="Authoritative orchestrator verdict passed",
                created_at=datetime(2026, 4, 21, 9, 0, tzinfo=UTC),
            ),
            make_review_verdict(
                task_id=bundle.contract.task_id,
                verdict_id="RV-2026032",
                category="statistical",
                result="fail",
                summary="One layer-specific failure landed later",
                confidence_score=0.11,
                created_at=datetime(2026, 4, 21, 9, 30, tzinfo=UTC),
            ),
        ]
    )
    bundle.delivery_pack = make_delivery_pack(task_id=bundle.contract.task_id)

    TaskContractStateMachine.validate_transition(bundle, TaskContractStatus.CLOSED)

    effective = TaskContractValidator.get_effective_review_verdict(bundle)
    assert effective is not None
    assert effective.verdict_id == "RV-2026031"
    assert "Latest verifier=pass | confidence=medium | blocking_issues=0" in (
        TaskContractValidator.build_dod_summary(bundle)
    )
