from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


def _verified_query_payload() -> dict[str, object]:
    return {
        "vq_id": "vq_churn_001",
        "metric_id": "monthly_churn_rate",
        "dialect": "postgres",
        "description": "Monthly churn by month",
        "sql_template": (
            "SELECT * FROM churn "
            "WHERE month >= {{start_date}} AND month < {{end_date}}"
        ),
        "parameters": [
            {"name": "start_date", "type": "date", "description": "inclusive start"},
            {"name": "end_date", "type": "date", "description": "exclusive end"},
        ],
        "referenced_tables": ["prod.growth.subscription"],
        "verified_by": "analyst@corp.example",
        "last_verified": date(2026, 4, 15),
        "verification_evidence": "Dashboard 47 parity",
    }


def test_verified_query_accepts_matching_placeholders() -> None:
    query = VerifiedQuery(**_verified_query_payload())

    assert [parameter.name for parameter in query.parameters] == ["start_date", "end_date"]


def test_verified_query_rejects_placeholder_mismatch() -> None:
    payload = _verified_query_payload()
    payload["parameters"] = [
        {"name": "start_date", "type": "date", "description": "inclusive start"}
    ]

    with pytest.raises(ValidationError, match="placeholders"):
        VerifiedQuery(**payload)
