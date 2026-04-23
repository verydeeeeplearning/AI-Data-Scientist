"""Use case: build a daily/weekly digest from notification history.

Pulls digest entries via a port, then defers to the domain
:func:`aggregate_digest` for the actual aggregation.  Adapters render
the resulting :class:`Digest` for whichever surface (Telegram, e-mail).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ds_agent.domain.notification import (
    Digest,
    DigestCadence,
    DigestEntry,
    aggregate_digest,
)


class DigestEntrySourcePort(Protocol):
    """Output port that returns digest entries in a (window-bounded) range."""

    def list_entries(
        self,
        *,
        operator_id: str,
        since: datetime,
        until: datetime,
    ) -> list[DigestEntry]: ...


@dataclass(slots=True)
class BuildDigestResult:
    digest: Digest
    operator_id: str


class BuildDigestUseCase:
    """Aggregate operator events into a digest for *cadence*."""

    def __init__(self, source: DigestEntrySourcePort) -> None:
        self._source = source

    def execute(
        self,
        *,
        operator_id: str,
        cadence: DigestCadence,
        now: datetime,
        top_n: int = 3,
    ) -> BuildDigestResult:
        if cadence is DigestCadence.OFF:
            digest = aggregate_digest([], cadence=cadence, now=now, top_n=top_n)
            return BuildDigestResult(digest=digest, operator_id=operator_id)

        since = now - cadence.window
        entries = self._source.list_entries(
            operator_id=operator_id,
            since=since,
            until=now,
        )
        digest = aggregate_digest(entries, cadence=cadence, now=now, top_n=top_n)
        return BuildDigestResult(digest=digest, operator_id=operator_id)
