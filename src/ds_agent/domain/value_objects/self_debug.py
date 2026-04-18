"""Self-debugging domain value objects.

Defines error categories and debug decisions used by the SelfDebugHook.
These belong to the domain layer — no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCategory(StrEnum):
    """Classification of tool errors for self-debugging."""

    DATA_ERROR = "data_error"  # FileNotFound, encoding, schema mismatch
    CODE_BUG = "code_bug"  # TypeError, IndexError, ValueError
    ENV_ERROR = "env_error"  # OOM, timeout, missing package
    LOGIC_ERROR = "logic_error"  # wrong join, leakage, wrong metric
    UNKNOWN = "unknown"


class DebugAction(StrEnum):
    """Action the self-debug loop should take."""

    RETRY = "retry"  # Suggest fix and retry
    ESCALATE = "escalate"  # Max retries exceeded, ask user
    SKIP = "skip"  # Non-retriable, skip this tool


@dataclass(frozen=True, slots=True)
class SelfDebugDecision:
    """Immutable decision produced by error analysis.

    Encapsulates what the self-debug hook decides to do after
    encountering a tool error.
    """

    action: DebugAction
    error_category: ErrorCategory
    suggestion: str
    attempt_count: int
    error_signature: str  # hash of error type + core message
    previous_signatures: tuple[str, ...] = ()

    @property
    def is_repeated_error(self) -> bool:
        """True if the same error signature appeared before."""
        return self.error_signature in self.previous_signatures

    @property
    def should_retry(self) -> bool:
        return self.action == DebugAction.RETRY

    @property
    def should_escalate(self) -> bool:
        return self.action == DebugAction.ESCALATE
