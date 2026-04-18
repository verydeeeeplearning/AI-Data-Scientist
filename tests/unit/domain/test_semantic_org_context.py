from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ds_agent.memory.semantic.domain.org_context import CalendarEvent, NegativeKnowledge


def test_calendar_event_requires_non_reversed_range() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        CalendarEvent(
            event_id="freeze.q2",
            type="freeze",
            name="Quarter close freeze",
            start_date=datetime(2026, 4, 20, tzinfo=UTC).date(),
            end_date=datetime(2026, 4, 10, tzinfo=UTC).date(),
            description="No schema changes",
        )


def test_negative_knowledge_requires_distinct_corrective_path() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        NegativeKnowledge(
            nk_id="nk-1",
            topic="monthly_churn_rate",
            wrong_approach="promo_flag = TRUE",
            why_wrong="biases churn downward",
            correct_approach="promo_flag = TRUE",
            recorded_at=datetime(2026, 4, 16, tzinfo=UTC),
            recorded_by="retrospective",
        )

