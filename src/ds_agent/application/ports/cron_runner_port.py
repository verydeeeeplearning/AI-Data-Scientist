"""Port: ``CronRunnerPort`` — abstraction for cron expression evaluation.

The application layer depends only on this Protocol. Concrete cron
evaluators live in ``ds_agent.infrastructure`` and are wired at the
composition root.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.standing_order import CronTrigger


@runtime_checkable
class CronRunnerPort(Protocol):
    """Contract any cron-expression evaluator must honour."""

    def matches(self, trigger: CronTrigger, *, now: datetime | None = None) -> bool:
        """Return whether ``trigger`` is due at ``now`` (or the current instant)."""

    def next_run(self, trigger: CronTrigger, *, after: datetime | None = None) -> datetime:
        """Return the next instant ``trigger`` fires after ``after`` (or the current instant)."""
