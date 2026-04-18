"""Infrastructure errors for warehouse adapters."""

from __future__ import annotations


class ReadOnlyViolationError(ValueError):
    """Raised when a read-only adapter receives a write query."""


class ConnectorDependencyError(RuntimeError):
    """Raised when an optional connector dependency is unavailable."""
