from __future__ import annotations

import re
from pathlib import Path

from ds_agent.domain.value_objects.use_case_mapping import (
    ONBOARDING_USE_CASE_IDS,
    USE_CASE_SPECS,
    resolve_use_case,
)


def test_every_onboarding_use_case_id_has_a_python_spec() -> None:
    assert set(ONBOARDING_USE_CASE_IDS) == set(USE_CASE_SPECS)


def test_resolve_use_case_falls_back_to_general_spec() -> None:
    assert resolve_use_case("missing-id").use_case_id == "general"


def test_real_onboarding_use_cases_resolve_to_mission_packs() -> None:
    assert resolve_use_case("data_analysis").default_mission == "data_analysis"
    assert resolve_use_case("reporting").default_mission == "reporting"
    assert resolve_use_case("prediction").default_mission == "prediction"
    assert resolve_use_case("dashboard").default_mission == "dashboard"
    assert resolve_use_case("sql_exploration").default_mission == "sql_exploration"
    assert resolve_use_case("weekly_kpi_triage").default_mission == "weekly-kpi-triage"
    assert resolve_use_case("ab_test_analysis").default_mission == "ab-test-analysis"
    assert resolve_use_case("general").default_mission == "general"


def test_every_onboarding_use_case_now_has_a_default_mission() -> None:
    assert all(spec.default_mission for spec in USE_CASE_SPECS.values())


def test_every_onboarding_use_case_now_has_a_default_audience() -> None:
    assert all(spec.default_audience.value for spec in USE_CASE_SPECS.values())


def test_typescript_twin_matches_python_use_case_ids_contract_types_missions_and_audiences() -> (
    None
):
    repo_root = Path(__file__).resolve().parents[3]
    ts_path = repo_root / "electron" / "src" / "shared" / "useCaseMapping.ts"
    source = ts_path.read_text(encoding="utf-8")

    use_case_ids = set(re.findall(r"useCaseId:\s*'([^']+)'", source))
    contract_types = {
        use_case_id: contract_type
        for use_case_id, contract_type in re.findall(
            r"([a-z_]+):\s*\{[\s\S]*?contractType:\s*'([^']+)'",
            source,
        )
    }
    default_missions = {
        use_case_id: (mission or None)
        for use_case_id, mission in re.findall(
            r"([a-z_]+):\s*\{[\s\S]*?defaultMission:\s*(?:'([^']+)'|null)",
            source,
        )
    }
    default_audiences = {
        use_case_id: audience
        for use_case_id, audience in re.findall(
            r"([a-z_]+):\s*\{[\s\S]*?defaultAudience:\s*'([^']+)'",
            source,
        )
    }

    assert use_case_ids == set(ONBOARDING_USE_CASE_IDS)
    assert contract_types == {
        use_case_id: spec.contract_type for use_case_id, spec in USE_CASE_SPECS.items()
    }
    assert default_missions == {
        use_case_id: spec.default_mission for use_case_id, spec in USE_CASE_SPECS.items()
    }
    assert default_audiences == {
        use_case_id: spec.default_audience.value for use_case_id, spec in USE_CASE_SPECS.items()
    }
