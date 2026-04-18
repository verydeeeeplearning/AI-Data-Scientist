from __future__ import annotations

from datetime import date

import pytest

from ds_agent.memory.semantic.domain.trust import RefreshSLA, TableTrust, TrustGrade


def test_untrusted_cannot_jump_directly_to_gold() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        TrustGrade.UNTRUSTED.validate_transition(TrustGrade.GOLD)


def test_table_trust_allows_one_step_promotion() -> None:
    table = TableTrust(
        fqtn="prod.growth.subscription",
        grade=TrustGrade.BRONZE,
        owner="growth_team",
        description="subscription fact",
        refresh=RefreshSLA(cadence="daily", max_staleness_minutes=1440),
        grade_rationale="awaiting audit",
        last_audited=date(2026, 4, 1),
    )

    promoted = table.transition_grade(TrustGrade.SILVER)

    assert promoted.grade is TrustGrade.SILVER

