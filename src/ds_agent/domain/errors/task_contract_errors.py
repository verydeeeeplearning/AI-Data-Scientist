"""Domain errors for task contract workflows."""

from __future__ import annotations


class TaskContractError(Exception):
    """Base class for all task contract domain errors."""

    error_code = "TASK_CONTRACT_ERROR"


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
