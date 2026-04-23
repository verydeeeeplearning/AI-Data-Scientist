"""Domain table tests for push eligibility (Wave 4 PLAN_06b).

Pinning the predicate against every category guards the ADR: if anyone
flips INFO/MILESTONE/DIGEST to push-eligible (the original anti-pattern
this plan exists to avoid) the test must fail loudly.
"""

from __future__ import annotations

import pytest

from ds_agent.domain.notification import (
    PUSH_ELIGIBLE_CATEGORIES,
    NotificationCategory,
    is_push_eligible,
)


@pytest.mark.parametrize(
    "category,expected",
    [
        (NotificationCategory.INFO, False),
        (NotificationCategory.MILESTONE, False),
        (NotificationCategory.DIGEST, False),
        (NotificationCategory.APPROVAL, True),
        (NotificationCategory.ERROR, True),
    ],
)
def test_is_push_eligible_table(
    category: NotificationCategory,
    expected: bool,
) -> None:
    assert is_push_eligible(category) is expected


def test_push_eligible_categories_set_is_frozen() -> None:
    """Callers must not be able to mutate the policy at runtime."""
    assert isinstance(PUSH_ELIGIBLE_CATEGORIES, frozenset)
    assert (
        frozenset({NotificationCategory.APPROVAL, NotificationCategory.ERROR})
        == PUSH_ELIGIBLE_CATEGORIES
    )
    with pytest.raises(AttributeError):
        # frozenset has no .add — confirms immutability.
        PUSH_ELIGIBLE_CATEGORIES.add(NotificationCategory.INFO)  # type: ignore[attr-defined]


def test_push_eligibility_aligns_with_quiet_hours_bypass() -> None:
    """The two predicates happen to coincide today — pin that explicitly.

    The ADR notes they are conceptually separate; a future divergence
    will surface here as a test failure that forces the author to update
    BOTH the predicate and this test together.
    """
    for category in NotificationCategory:
        assert is_push_eligible(category) == category.bypasses_quiet_hours
