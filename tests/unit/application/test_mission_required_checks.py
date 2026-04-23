from __future__ import annotations

import pytest

from ds_agent.application.services.mission_required_checks import MissionRequiredCheckResolver
from ds_agent.skills.mission_pack_loader import MissionPackLoader


@pytest.mark.parametrize("mission_name", MissionPackLoader().list_packs())
def test_current_mission_packs_resolve_against_verifier_inventory(
    mission_name: str,
) -> None:
    resolver = MissionRequiredCheckResolver(MissionPackLoader())

    resolution = resolver.resolve_for_mission(mission_name)

    assert resolution is not None
    assert resolution.mission_loaded is True
    assert resolution.unmapped_required_checks == ()
    assert set(resolution.mapped_required_checks).issubset(set(resolution.required_checks))


def test_reporting_pack_maps_executive_narrative_review_to_existing_verifier_checks() -> None:
    resolver = MissionRequiredCheckResolver(MissionPackLoader())

    resolution = resolver.resolve_for_mission("reporting")

    assert resolution is not None
    assert resolution.mapped_required_checks["executive_narrative_review"] == (
        "business_question_confirmed",
        "claim_evidence_alignment",
        "overstatement_hedge_detection",
        "recommendation_feasibility",
    )


def test_missing_mission_pack_is_marked_unloaded() -> None:
    resolver = MissionRequiredCheckResolver(MissionPackLoader())

    resolution = resolver.resolve_for_mission("definitely-missing-mission")

    assert resolution is not None
    assert resolution.mission_name == "definitely-missing-mission"
    assert resolution.mission_loaded is False
    assert resolution.required_checks == ()
