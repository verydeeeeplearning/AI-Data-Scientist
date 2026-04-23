from ds_agent.agent.prompt_sections import build_missing_mission_section, build_mission_section
from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.skills.mission_pack_loader import MissionPackLoader


def _mission_pack() -> MissionPack:
    return MissionPack.model_validate(
        {
            "name": "weekly-kpi-triage",
            "version": 1,
            "summary": "Weekly KPI anomaly triage.",
            "authority_default": "delegate",
            "audience_default": "senior_staff",
            "skills_required": ["hypothesis-ranking"],
            "boundary": {
                "allowed_data_domains": ["growth", "sales", "marketing"],
                "required_semantic_metrics": ["dau"],
                "allowed_action_classes": ["read_sql_gold", "jira_create"],
            },
            "required_checks": ["schema_drift", "baseline_compare"],
            "required_artifacts": ["exec_brief"],
            "required_delivery_channels": ["jira_ticket"],
            "auto_escalate_when": ["confidence_low"],
            "success_criteria": ["issue_classified"],
        }
    )


def test_build_mission_section_renders_boundary_and_artifacts() -> None:
    section = build_mission_section(_mission_pack())

    assert "MISSION: weekly-kpi-triage (v1)" in section
    assert "boundary.allowed_data_domains: growth, sales, marketing" in section
    assert "required_artifacts: exec_brief" in section
    assert "required_delivery_channels: jira_ticket" in section


def test_build_missing_mission_section_is_conservative() -> None:
    section = build_missing_mission_section("weekly-kpi-triage")

    assert "MISSION: weekly-kpi-triage" in section
    assert "definition unavailable" in section
    assert "escalate ambiguity" in section


def test_build_mission_section_renders_all_real_phase4_pack_names() -> None:
    loader = MissionPackLoader()

    for name in (
        "ab-test-analysis",
        "dashboard",
        "general",
        "reporting",
    ):
        section = build_mission_section(loader.load(name))

        assert f"MISSION: {name} (v1)" in section
        assert "- required_checks:" in section
        assert "- required_artifacts:" in section
        assert "- success_criteria:" in section
