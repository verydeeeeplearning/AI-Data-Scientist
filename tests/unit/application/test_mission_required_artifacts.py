from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.services.mission_required_artifacts import (
    DELIVERY_ARTIFACT_IDS,
    MissionRequiredArtifactResolver,
)
from ds_agent.domain.entities.delivery_pack import DeliveryPack
from ds_agent.domain.entities.task_contract import TaskContract, TaskContractStatus
from ds_agent.domain.entities.task_contract_bundle import TaskContractBundle
from ds_agent.skills.mission_pack_loader import MissionPackLoader


def _bundle(
    *,
    mission: str,
    required_deliverables: list[dict[str, str]],
    delivery_items: list[dict[str, object]] | None = None,
) -> TaskContractBundle:
    now = datetime(2026, 4, 21, tzinfo=UTC)
    bundle = TaskContractBundle(
        contract=TaskContract(
            task_id="TC-2026-001",
            session_id="session-1",
            type="analysis",
            status=TaskContractStatus.IN_PROGRESS,
            business_goal="Answer the KPI question",
            mission=mission,
            required_deliverables=required_deliverables,
            created_at=now,
            updated_at=now,
        )
    )
    if delivery_items is not None:
        bundle.delivery_pack = DeliveryPack(
            pack_id="DP-1",
            task_id=bundle.contract.task_id,
            generated_at=now,
            items=delivery_items,
        )
    return bundle.sync_references()


def test_data_analysis_artifacts_resolve_and_detect_missing_delivery() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="data_analysis",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
        delivery_items=[
            {
                "deliverable_type": "exec_brief",
                "audience": "executive",
                "format": "pptx",
                "artifact_path": "reports/exec.pptx",
                "delivered": True,
            }
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mission_loaded is True
    assert resolution.mapped_required_artifacts == {
        "exec_brief": ("exec_brief",),
        "ds_appendix": ("ds_appendix",),
    }
    assert resolution.unmapped_required_artifacts == ()
    assert resolution.missing_contract_artifacts == ()
    assert resolution.missing_delivery_artifacts == ("ds_appendix",)


def test_weekly_kpi_triage_artifacts_no_longer_treat_jira_ticket_as_an_artifact() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="weekly-kpi-triage",
        required_deliverables=[
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mission_loaded is True
    assert resolution.required_artifacts == ("exec_brief", "ds_appendix")
    assert resolution.unmapped_required_artifacts == ()
    assert resolution.missing_contract_artifacts == ()


def test_prediction_marks_unmapped_artifact_families() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="prediction",
        required_deliverables=[
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {
                "type": "ds_experiment_note",
                "audience": "ds_peer",
                "format": "markdown",
            },
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mapped_required_artifacts == {
        "ds_appendix": ("ds_appendix",),
        "evaluation_report": ("ds_experiment_note",),
        "model_card": ("ml_handoff_spec",),
    }
    assert resolution.unmapped_required_artifacts == ()


def test_prediction_alias_maps_model_card_to_ml_handoff_spec() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="prediction",
        required_deliverables=[
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {
                "type": "ds_experiment_note",
                "audience": "ds_peer",
                "format": "markdown",
            },
            {"type": "ml_handoff_spec", "audience": "ml_engineer", "format": "markdown"},
        ],
        delivery_items=[
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
            {
                "deliverable_type": "ds_experiment_note",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/evaluation.md",
                "delivered": True,
            },
            {
                "deliverable_type": "ml_handoff_spec",
                "audience": "ml_engineer",
                "format": "markdown",
                "artifact_path": "reports/handoff.md",
                "delivered": True,
            },
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mapped_required_artifacts["model_card"] == ("ml_handoff_spec",)
    assert resolution.missing_contract_artifacts == ()
    assert resolution.missing_delivery_artifacts == ()
    assert resolution.unmapped_required_artifacts == ()


def test_prediction_alias_maps_evaluation_report_to_ds_experiment_note() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="prediction",
        required_deliverables=[
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {
                "type": "ds_experiment_note",
                "audience": "ds_peer",
                "format": "markdown",
            },
            {"type": "ml_handoff_spec", "audience": "ml_engineer", "format": "markdown"},
        ],
        delivery_items=[
            {
                "deliverable_type": "ds_appendix",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/appendix.md",
                "delivered": True,
            },
            {
                "deliverable_type": "ds_experiment_note",
                "audience": "ds_peer",
                "format": "markdown",
                "artifact_path": "reports/evaluation.md",
                "delivered": True,
            },
            {
                "deliverable_type": "ml_handoff_spec",
                "audience": "ml_engineer",
                "format": "markdown",
                "artifact_path": "reports/handoff.md",
                "delivered": True,
            },
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mapped_required_artifacts["evaluation_report"] == ("ds_experiment_note",)
    assert resolution.missing_contract_artifacts == ()
    assert resolution.missing_delivery_artifacts == ()
    assert resolution.unmapped_required_artifacts == ()


def test_current_mission_packs_resolve_against_delivery_vocabulary() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    required_deliverables = [
        {"type": artifact_id, "audience": "ds_peer", "format": "markdown"}
        for artifact_id in DELIVERY_ARTIFACT_IDS
    ]

    for mission_name in MissionPackLoader().list_packs():
        resolution = resolver.resolve_for_bundle(
            _bundle(
                mission=mission_name,
                required_deliverables=required_deliverables,
            )
        )

        assert resolution is not None
        assert resolution.mission_loaded is True
        assert resolution.unmapped_required_artifacts == ()


def test_sql_exploration_alias_maps_sql_notes_to_existing_delivery_artifacts() -> None:
    resolver = MissionRequiredArtifactResolver(MissionPackLoader())
    bundle = _bundle(
        mission="sql_exploration",
        required_deliverables=[
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ],
    )

    resolution = resolver.resolve_for_bundle(bundle)

    assert resolution is not None
    assert resolution.mapped_required_artifacts["sql_notes"] == ("notebook", "ds_appendix")
    assert resolution.missing_contract_artifacts == ()
