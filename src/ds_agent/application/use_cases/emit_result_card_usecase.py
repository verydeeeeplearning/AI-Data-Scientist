"""Emit and persist result cards from LLM response content."""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ds_agent.domain.result_card import (
    ResultCard,
    ResultCardSource,
    coerce_result_card,
)

_CARD_BLOCK_RE = re.compile(
    r"<card\s+type=\"(?P<type>[^\"]+)\">(?P<body>.*?)</card>",
    re.IGNORECASE | re.DOTALL,
)
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class Clock(Protocol):
    """Abstraction over wall-clock time for deterministic testing."""

    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    """Creates stable card identifiers."""

    def new_card_id(self) -> str: ...

    def new_result_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class EmittedResultCards:
    """Output of one emit operation."""

    stripped_message: str
    cards: list[ResultCard]


def _default_card_id() -> str:
    timestamp_ms = int(time.time() * 1000)
    randomness = secrets.randbits(80)
    return _encode_crockford(timestamp_ms, 10) + _encode_crockford(randomness, 16)


def _default_result_id() -> str:
    timestamp_ms = int(time.time() * 1000)
    randomness = secrets.randbits(80)
    return f"res_{_encode_crockford(timestamp_ms, 10)}{_encode_crockford(randomness, 16)}"


def _encode_crockford(value: int, length: int) -> str:
    encoded = ["0"] * length
    remaining = value
    for index in range(length - 1, -1, -1):
        encoded[index] = _CROCKFORD_BASE32[remaining & 31]
        remaining >>= 5
    return "".join(encoded)


def _extract_card_blocks(message: str) -> tuple[str, list[tuple[str, str]]]:
    parts: list[str] = []
    blocks: list[tuple[str, str]] = []
    last_end = 0
    for match in _CARD_BLOCK_RE.finditer(message):
        parts.append(message[last_end : match.start()])
        blocks.append((match.group("type"), match.group("body")))
        last_end = match.end()
    parts.append(message[last_end:])
    return ("".join(parts), blocks)


def _parse_payload(body: str) -> Mapping[str, object] | str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(payload, Mapping):
        return dict(payload)
    return body


class ResultCardStorePort(Protocol):
    """Persistence contract for emitted result cards."""

    def save_card(self, *, session_id: str, card: ResultCard) -> None: ...


class EmitResultCardUseCase:
    """Extract result cards from a response and persist them."""

    def __init__(
        self,
        store: ResultCardStorePort,
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or _SystemClock()
        self._ids = ids

    def execute(
        self,
        *,
        session_id: str,
        run_id: str,
        message_id: str,
        content: str,
        tool_call_id: str | None = None,
    ) -> EmittedResultCards:
        stripped_message, blocks = _extract_card_blocks(content)
        now = self._clock.now()
        source = ResultCardSource(
            messageId=message_id,
            runId=run_id,
            toolCallId=tool_call_id,
        )

        cards: list[ResultCard] = []
        for card_type, body in blocks:
            payload = _parse_payload(body)
            card = coerce_result_card(
                card_type,
                payload,
                card_id=self._new_card_id(),
                result_id=self._new_result_id(),
                created_at=now,
                source=source,
            )
            self._store.save_card(session_id=session_id, card=card)
            cards.append(card)

        return EmittedResultCards(stripped_message=stripped_message, cards=cards)

    def _new_card_id(self) -> str:
        if self._ids is None:
            return _default_card_id()
        return self._ids.new_card_id()

    def _new_result_id(self) -> str:
        if self._ids is None:
            return _default_result_id()
        return self._ids.new_result_id()


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
