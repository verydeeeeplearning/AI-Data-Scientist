"""Domain errors for task contract workflows."""

from __future__ import annotations

from collections.abc import Mapping


class TaskContractError(Exception):
    """Base class for all task contract domain errors."""

    error_code = "TASK_CONTRACT_ERROR"

    def __init__(
        self,
        message: str = "",
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})

    def to_api_detail(self) -> dict[str, object]:
        detail: dict[str, object] = {
            "message": str(self),
            "error_code": self.error_code,
        }
        if self.metadata:
            detail["metadata"] = self.metadata
        return detail


class TaskContractNotFoundError(TaskContractError):
    """Raised when the requested contract does not exist."""

    error_code = "TASK_CONTRACT_NOT_FOUND"


class TaskContractStateError(TaskContractError):
    """Raised when a state-machine rule is violated."""

    error_code = "TASK_CONTRACT_STATE_ERROR"


class InvalidTransitionError(TaskContractStateError):
    """Raised when a transition is not allowed."""

    error_code = "INVALID_TRANSITION"


class DoDUnmetError(TaskContractStateError):
    """Raised when closure preconditions are not met."""

    error_code = "DOD_UNMET"


class VersionConflictError(TaskContractError):
    """Raised when optimistic locking detects a stale writer."""

    error_code = "VERSION_CONFLICT"
