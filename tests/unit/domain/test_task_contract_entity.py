from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


def _base_contract_payload() -> dict[str, object]:
    now = datetime(2026, 4, 15, tzinfo=UTC)
    return {
        "task_id": "TC-2026-001",
        "session_id": "session-1",
        "type": "churn_analysis",
        "business_goal": "Reduce churn by one point",
        "required_deliverables": [
            {"type": "exec_brief", "audience": "executive", "format": "pptx"}
        ],
        "created_at": now,
        "updated_at": now,
    }


def test_invalid_task_id_pattern_raises() -> None:
    payload = _base_contract_payload()
    payload["task_id"] = "bad-id"
    with pytest.raises(ValidationError):
        TaskContract(**payload)


def test_empty_deliverables_raise() -> None:
    payload = _base_contract_payload()
    payload["required_deliverables"] = []
    with pytest.raises(ValidationError):
        TaskContract(**payload)


def test_authority_audience_and_mission_are_coerced() -> None:
    payload = _base_contract_payload()
    payload["authority"] = "delegate"
    payload["audience"] = "executive"
    payload["mission"] = "weekly-kpi-triage"

    contract = TaskContract(**payload)

    assert contract.authority == AuthorityMode.DELEGATE
    assert contract.audience == AudiencePersona.EXECUTIVE
    assert contract.mission == "weekly-kpi-triage"


def test_definition_of_done_accepts_verifier_requirements() -> None:
    payload = _base_contract_payload()
    payload["definition_of_done"] = {
        "criteria": ["Verifier confidence is at least medium"],
        "verifier": {
            "min_result": "warn",
            "min_confidence_grade": "medium",
            "require_no_blocking_issues": True,
        },
    }

    contract = TaskContract(**payload)

    assert contract.definition_of_done is not None
    assert contract.definition_of_done.verifier is not None
    assert contract.definition_of_done.verifier.min_result == "warn"
    assert contract.definition_of_done.verifier.min_confidence_grade == "medium"
    assert contract.definition_of_done.verifier.require_no_blocking_issues is True
