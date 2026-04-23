from pydantic import ValidationError

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


def _mission_payload() -> dict[str, object]:
    return {
        "name": "weekly-kpi-triage",
        "version": 1,
        "summary": "Weekly KPI anomaly triage.",
        "authority_default": "delegate",
        "audience_default": "senior_staff",
        "skills_required": ["hypothesis-ranking"],
        "boundary": {
            "allowed_data_domains": ["growth", "sales"],
            "required_semantic_metrics": ["dau"],
            "allowed_action_classes": ["read_sql_gold"],
        },
        "required_checks": ["schema_drift"],
        "required_artifacts": ["exec_brief"],
        "required_delivery_channels": ["jira_ticket"],
        "auto_escalate_when": ["confidence_low"],
        "success_criteria": ["issue_classified"],
    }


def test_mission_pack_coerces_default_authority_and_audience() -> None:
    pack = MissionPack.model_validate(_mission_payload())

    assert pack.authority_default is AuthorityMode.DELEGATE
    assert pack.audience_default is AudiencePersona.SENIOR_STAFF
    assert pack.boundary.allowed_data_domains == ("growth", "sales")


def test_mission_pack_requires_boundary_and_required_lists() -> None:
    payload = _mission_payload()
    payload["boundary"] = {
        "allowed_data_domains": [],
        "required_semantic_metrics": [],
        "allowed_action_classes": [],
    }

    try:
        MissionPack.model_validate(payload)
    except ValidationError as exc:
        assert "allowed_data_domains" in str(exc)
    else:
        raise AssertionError("Expected validation error for empty allowed_data_domains")


def test_mission_pack_rejects_blank_required_artifacts() -> None:
    payload = _mission_payload()
    payload["required_artifacts"] = [" "]

    try:
        MissionPack.model_validate(payload)
    except ValidationError as exc:
        assert "required_artifacts" in str(exc)
    else:
        raise AssertionError("Expected validation error for blank required_artifacts")


def test_mission_pack_rejects_blank_required_delivery_channels() -> None:
    payload = _mission_payload()
    payload["required_delivery_channels"] = [" "]

    try:
        MissionPack.model_validate(payload)
    except ValidationError as exc:
        assert "required_delivery_channels" in str(exc)
    else:
        raise AssertionError("Expected validation error for blank required_delivery_channels")


def test_mission_pack_policy_override_returns_mission_local_verdict() -> None:
    payload = _mission_payload()
    payload["action_policy_overrides"] = {"jira_create": {"delegate": "auto"}}

    pack = MissionPack.model_validate(payload)

    assert pack.policy_override("jira_create", "delegate") == "auto"
    assert pack.policy_override("jira_create", "supervised") is None


def test_mission_pack_boundary_checks_action_class_and_domain() -> None:
    payload = _mission_payload()
    payload["boundary"]["allowed_action_classes"] = ["jira_create"]

    pack = MissionPack.model_validate(payload)

    assert pack.is_within_boundary("jira_create", {"data_domain": "growth"}) is True
    assert pack.is_within_boundary("jira_create", {"data_domain": "finance"}) is False
    assert pack.is_within_boundary("prod_deploy", {"data_domain": "growth"}) is False


def test_mission_pack_certification_spec_is_available() -> None:
    payload = _mission_payload()
    payload["certification"] = {
        "current_level": "delegate",
        "next_target": "autopilot",
        "autopilot_requirements": {
            "shadow_runs_passed": 10,
            "critical_violations": 0,
            "verifier_avg_score": 0.85,
            "rollback_rehearsal": "passed",
            "owner_approvals": 2,
        },
    }

    pack = MissionPack.model_validate(payload)

    assert pack.certification is not None
    assert pack.certification.current_level is not None
    assert pack.certification.current_level.value == "delegate"
    assert pack.certification.autopilot_requirements is not None
    assert pack.certification.autopilot_requirements.owner_approvals == 2
