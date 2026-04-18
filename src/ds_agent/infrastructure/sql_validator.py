"""Infrastructure-facing SQL validator wrapper."""

from __future__ import annotations

from ds_agent.domain.value_objects.connector import SqlValidationResult, validate_sql_safety


def validate_read_only_sql(sql: str) -> SqlValidationResult:
    """Validate SQL through the shared domain-level read-only validator."""
    return validate_sql_safety(sql)
