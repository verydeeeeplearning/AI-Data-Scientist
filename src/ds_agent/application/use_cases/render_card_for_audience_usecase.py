"""Render a persisted result card for a specific audience."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.result_card import ResultCard

CardAudience = Literal["ds", "exec", "ml"]


class RenderedCardSection(BaseModel):
    """One structured section in the audience-rendered card."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


class RenderedAudienceCard(BaseModel):
    """Backend-authored card body for one audience lens."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    summary: str | None = None
    body: str | None = None
    sections: list[RenderedCardSection] = Field(default_factory=list)


class CardLookupPort(Protocol):
    """Persistence contract for looking up one card."""

    def get_card(self, card_id: str) -> ResultCard | None: ...


class CardRenderingPort(Protocol):
    """Rendering contract for audience-specific card presentation."""

    def render(self, card: ResultCard, audience: CardAudience) -> RenderedAudienceCard: ...


class RenderCardForAudienceUseCase:
    """Load one card and render it for an audience view."""

    def __init__(
        self,
        *,
        store: CardLookupPort,
        renderer: CardRenderingPort,
    ) -> None:
        self._store = store
        self._renderer = renderer

    def execute(self, *, card_id: str, audience: CardAudience) -> RenderedAudienceCard:
        card = self._store.get_card(card_id)
        if card is None:
            raise LookupError(f"Card not found: {card_id}")
        return self._renderer.render(card, audience)
