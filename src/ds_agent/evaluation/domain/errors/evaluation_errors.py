"""Evaluation harness specific exceptions."""

from __future__ import annotations


class EvaluationError(Exception):
    """Base error for evaluation harness failures."""


class GoldTaskValidationError(EvaluationError):
    """Raised when a gold task file is invalid."""


class MissingEvalRunError(EvaluationError):
    """Raised when an expected eval run fixture cannot be found."""

