"""Memory hint builder for system prompt injection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ds_agent.memory.domain_kb import DomainKB

logger = structlog.get_logger()


class MemoryHintBuilder:
    """Build memory hints from DomainKB for prompt injection."""

    def __init__(
        self,
        domain_kb: DomainKB,
        max_tokens: int = 500,
    ) -> None:
        self._domain_kb = domain_kb
        self._max_tokens = max_tokens

    def build_hints(self, domain: str | None = None) -> str:
        """Build hints string from domain knowledge.

        Returns empty string if no relevant knowledge found.
        """
        hints = self._domain_kb.get_memory_hints(
            domain=domain,
            max_tokens=self._max_tokens,
        )

        if not hints:
            return ""

        # Truncate to max_tokens budget
        max_chars = self._max_tokens * 4
        if len(hints) > max_chars:
            hints = hints[:max_chars].rsplit("\n", 1)[0]

        return hints
