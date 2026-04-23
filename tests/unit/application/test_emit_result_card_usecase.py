from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.application.use_cases.emit_result_card_usecase import (
    EmitResultCardUseCase,
    EmittedResultCards,
)
from ds_agent.application.use_cases.list_cards_by_session_usecase import (
    ListCardsBySessionUseCase,
)
from ds_agent.application.use_cases.pin_card_usecase import PinCardUseCase
from ds_agent.domain.result_card import OtherCard, ResultCardSource, coerce_result_card

NOW = datetime(2026, 4, 19, 10, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequentialIds:
    def __init__(self) -> None:
        self._count = 0

    def new_card_id(self) -> str:
        self._count += 1
        return f"RC-{self._count:03d}"

    def new_result_id(self) -> str:
        self._count += 1
        return f"RESULT-{self._count:03d}"


class FakeCardStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str, object]] = []
        self.cards_by_id: dict[str, object] = {}

    def save_card(self, session_id: str, card):
        self.saved.append((session_id, card))
        self.cards_by_id[card.card_id] = card
        return card

    def get_card(self, card_id: str):
        return self.cards_by_id.get(card_id)

    def list_cards_by_session(
        self,
        session_id: str,
        *,
        limit: int = 100,
        include_archived: bool = False,
    ):
        cards = [card for sid, card in self.saved if sid == session_id]
        if not include_archived:
            cards = [card for card in cards if not card.archived]
        return cards[:limit]

    def pin_card(self, card_id: str, *, pinned: bool = True):
        card = self.cards_by_id[card_id]
        if not isinstance(pinned, bool):
            raise ValueError("pinned must be a boolean")
        updated = card.model_copy(update={"pinned": pinned})
        self.cards_by_id[card_id] = updated
        for idx, (session_id, saved_card) in enumerate(self.saved):
            if saved_card.card_id == card_id:
                self.saved[idx] = (session_id, updated)
                break
        return updated


def test_emit_result_card_usecase_extracts_cards_and_strips_message() -> None:
    store = FakeCardStore()
    use_case = EmitResultCardUseCase(store=store, clock=FixedClock(), ids=SequentialIds())

    result = use_case.execute(
        session_id="session-1",
        run_id="run-1",
        message_id="msg-1",
        content=(
            "Lead line\n"
            "<card type=\"insight\">"
            "{\"title\":\"Retention\",\"evidence\":[\"cohort\"],"
            "\"trustStatus\":\"pending\",\"quickActions\":[]}"
            "</card>\n"
            "Tail line"
        ),
    )

    assert isinstance(result, EmittedResultCards)
    assert result.stripped_message == "Lead line\n\nTail line"
    assert len(result.cards) == 1
    assert result.cards[0].card_id == "RC-001"
    assert result.cards[0].result_id == "RESULT-002"
    assert result.cards[0].type == "insight"
    assert store.saved[0][0] == "session-1"


def test_emit_result_card_usecase_falls_back_to_other() -> None:
    store = FakeCardStore()
    use_case = EmitResultCardUseCase(store=store, clock=FixedClock(), ids=SequentialIds())

    result = use_case.execute(
        session_id="session-2",
        run_id="run-2",
        message_id="msg-2",
        content='<card type="risk">not json</card>',
    )

    assert len(result.cards) == 1
    assert isinstance(result.cards[0], OtherCard)
    assert result.cards[0].body == "not json"


def test_emit_result_card_usecase_parses_experiment_card_payload() -> None:
    store = FakeCardStore()
    use_case = EmitResultCardUseCase(store=store, clock=FixedClock(), ids=SequentialIds())

    result = use_case.execute(
        session_id="session-3",
        run_id="run-3",
        message_id="msg-3",
        content=(
            "<card type=\"experiment\">"
            "{\"runId\":\"run-3\",\"modelLabel\":\"XGBoost\",\"dataVersion\":\"dataset-v4\","
            "\"primaryMetric\":{\"name\":\"roc_auc\",\"value\":0.901,\"deltaVsBaseline\":0.013},"
            "\"artifactRefs\":[{\"artifactId\":\"artifact-3\",\"ref\":\"artifact://chart-3\"}]}"
            "</card>"
        ),
    )

    assert len(result.cards) == 1
    assert result.cards[0].type == "experiment"
    assert result.cards[0].primary_metric.name == "roc_auc"
    assert result.cards[0].primary_metric.value == pytest.approx(0.901)


def test_list_cards_by_session_usecase_reads_store() -> None:
    store = FakeCardStore()
    card = coerce_result_card(
        "insight",
        {
            "title": "Lift",
            "evidence": [],
            "trustStatus": "pending",
            "quickActions": [],
        },
        card_id="RC-9",
        result_id="result-9",
        created_at=NOW,
        source=ResultCardSource(messageId="msg-9", runId="run-9"),
    )
    store.save_card("session-9", card)

    use_case = ListCardsBySessionUseCase(store=store)
    cards = use_case.execute(session_id="session-9")

    assert len(cards) == 1
    assert cards[0].card_id == "RC-9"
    assert cards[0].result_id == "result-9"


def test_pin_card_usecase_updates_store() -> None:
    store = FakeCardStore()
    card = coerce_result_card(
        "insight",
        {
            "title": "Lift",
            "evidence": [],
            "trustStatus": "pending",
            "quickActions": [],
        },
        card_id="RC-10",
        result_id="result-10",
        created_at=NOW,
        source=ResultCardSource(messageId="msg-10", runId="run-10"),
    )
    store.save_card("session-10", card)

    use_case = PinCardUseCase(store=store)
    updated = use_case.execute(card_id="RC-10", pinned=True)

    assert updated.pinned is True
    assert store.get_card("RC-10").pinned is True


def test_pin_card_usecase_raises_for_missing_card() -> None:
    use_case = PinCardUseCase(store=FakeCardStore())

    with pytest.raises(KeyError):
        use_case.execute(card_id="missing")


def test_pin_card_usecase_rejects_non_boolean_input() -> None:
    use_case = PinCardUseCase(store=FakeCardStore())

    with pytest.raises(ValueError, match="pinned must be a boolean"):
        use_case.execute(card_id="missing", pinned="yes")  # type: ignore[arg-type]
