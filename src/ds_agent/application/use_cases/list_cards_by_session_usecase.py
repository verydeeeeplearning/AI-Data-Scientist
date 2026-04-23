"""List persisted result cards for one session."""

from __future__ import annotations

from typing import Protocol

from ds_agent.domain.result_card import ResultCard


class CardListingStore(Protocol):
    """Minimal read contract for result-card queries."""

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ResultCard]: ...


class ListCardsBySessionUseCase:
    """Return cards emitted for one session."""

    def __init__(self, store: CardListingStore) -> None:
        self._store = store

    def execute(
        self,
        *,
        session_id: str,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ResultCard]:
        return self._store.list_cards_by_session(
            session_id,
            limit=limit,
            include_archived=include_archived,
        )

