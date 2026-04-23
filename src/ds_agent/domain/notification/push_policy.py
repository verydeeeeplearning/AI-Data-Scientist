"""Push-eligibility domain predicate (Wave 4 PLAN_06b).

ADR
---
Mobile web push is **complementary** to Telegram, not a replacement.

Telegram already covers the high-noise notification surfaces (INFO,
MILESTONE, DIGEST). Push is reserved for the two categories where the
operator MUST act *now* on a phone:

* APPROVAL — operator must explicitly grant or reject.
* ERROR    — urgent failures the operator should know about immediately.

INFO / MILESTONE / DIGEST stay Telegram-or-in-app to avoid the well
documented "push fatigue" anti-pattern that erodes trust in the channel.

This module is **domain-pure** — no I/O, no framework, no external deps.
The predicate is encoded as data (a frozen set + a function) instead of
runtime if/elses sprinkled across adapters, so the policy has exactly one
source of truth.
"""

from __future__ import annotations

from ds_agent.domain.notification.notification import NotificationCategory

# Frozen set so callers can't mutate the policy from the outside.
PUSH_ELIGIBLE_CATEGORIES: frozenset[NotificationCategory] = frozenset(
    {
        NotificationCategory.APPROVAL,
        NotificationCategory.ERROR,
    }
)


def is_push_eligible(category: NotificationCategory) -> bool:
    """Return True iff *category* is allowed to fan out to web push.

    Reuses :pyattr:`NotificationCategory.bypasses_quiet_hours` semantics
    intentionally — the two surfaces happen to coincide today (APPROVAL
    and ERROR), but they remain *separate concepts*: quiet-hours bypass is
    about *when* a notification reaches the operator; push eligibility is
    about *which transports* a notification may use. They are kept as two
    distinct predicates so that a future policy change to either surface
    does not silently flip the other.
    """
    return category in PUSH_ELIGIBLE_CATEGORIES


__all__ = ["PUSH_ELIGIBLE_CATEGORIES", "is_push_eligible"]
