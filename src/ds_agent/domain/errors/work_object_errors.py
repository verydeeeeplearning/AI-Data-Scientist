"""Domain errors for workflow integration work objects."""

from __future__ import annotations


class WorkObjectError(Exception):
    """Base class for work-object related failures."""

    error_code = "WORK_OBJECT_ERROR"


class WorkObjectNotFoundError(WorkObjectError):
    """Raised when a work object does not exist."""

    error_code = "WORK_OBJECT_NOT_FOUND"


class WorkObjectAlreadyExistsError(WorkObjectError):
    """Raised when a task contract already has a linked work object."""

    error_code = "WORK_OBJECT_ALREADY_EXISTS"


class WorkObjectStateError(WorkObjectError):
    """Raised when lifecycle transitions or invariants are violated."""

    error_code = "WORK_OBJECT_STATE_ERROR"
