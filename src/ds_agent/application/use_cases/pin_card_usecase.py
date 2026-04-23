"""Pin or unpin one result card."""

from __future__ import annotations

from typing import Protocol

from ds_agent.domain.result_card import ResultCard, validate_bool_flag


class CardPinStore(Protocol):
    """Minimal mutation contract for result-card pinning."""

    def pin_card(self, card_id: str, *, pinned: bool = True) -> ResultCard: ...


class PinCardUseCase:
    """Update a result card's pinned state."""

    def __init__(self, store: CardPinStore) -> None:
        self._store = store

    def execute(self, *, card_id: str, pinned: bool = True) -> ResultCard:
        return self._store.pin_card(card_id, pinned=validate_bool_flag("pinned", pinned))
