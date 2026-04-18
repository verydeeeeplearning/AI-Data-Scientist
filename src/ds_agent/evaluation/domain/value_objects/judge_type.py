"""Judge type value object used by scorers."""

from __future__ import annotations

from enum import StrEnum


class JudgeType(StrEnum):
    """Execution mode for a scorer."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HYBRID = "hybrid"
    HUMAN_OR_PROXY = "human_or_proxy"

