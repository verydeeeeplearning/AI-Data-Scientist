"""Data connector domain value objects.

Defines connector configuration and query specifications.
Domain layer — no external dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

ConnectorOptionScalar = str | int | float | bool | None


class ConnectorType(StrEnum):
    """Supported warehouse connector types."""

    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    POSTGRES = "postgres"
    DATABRICKS = "databricks"


class CredentialMethod(StrEnum):
    """How credentials are supplied."""

    ENV = "env"
    SECRET_MANAGER = "secret_manager"
    OAUTH = "oauth"


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    """Immutable warehouse connector configuration.

    Credentials are NEVER stored directly — only references
    to environment variables or secret manager keys.
    """

    name: str = "default"
    type: ConnectorType = ConnectorType.POSTGRES
    label: str = ""
    options: dict[str, ConnectorOptionScalar] = field(default_factory=dict)
    host: str = ""
    database: str = ""
    schema: str = "public"
    credential_method: CredentialMethod = CredentialMethod.ENV
    credential_ref: str = ""  # env var name or secret key
    read_only: bool = True
    timeout_seconds: int = 30
    max_rows: int = 10_000

    def __post_init__(self) -> None:
        merged_options = dict(self.options)

        resolved_host = self.host or self._string_option(
            merged_options,
            "host",
            aliases=("account",),
        )
        if resolved_host:
            merged_options.setdefault("host", resolved_host)

        database_key = "project_id" if self.type == ConnectorType.BIGQUERY else "database"
        if self.database:
            merged_options.setdefault(database_key, self.database)

        resolved_database = self.database or self._string_option(
            merged_options,
            database_key,
        )

        default_schema = (
            "public" if self.type in {ConnectorType.POSTGRES, ConnectorType.SNOWFLAKE} else ""
        )
        resolved_schema = self.schema or self._string_option(
            merged_options,
            "schema",
            aliases=("dataset",),
            default=default_schema,
        )
        if resolved_schema and self.type in {ConnectorType.POSTGRES, ConnectorType.SNOWFLAKE}:
            merged_options.setdefault("schema", resolved_schema)

        if not resolved_database:
            required_field = "project_id" if self.type == ConnectorType.BIGQUERY else "database"
            raise ValueError(f"ConnectorConfig requires '{required_field}'")

        object.__setattr__(self, "label", self.label or self.name)
        object.__setattr__(self, "options", merged_options)
        object.__setattr__(self, "host", resolved_host)
        object.__setattr__(self, "database", resolved_database)
        object.__setattr__(self, "schema", resolved_schema or default_schema)

    def get_option(
        self,
        key: str,
        default: ConnectorOptionScalar = None,
        *,
        aliases: tuple[str, ...] = (),
    ) -> ConnectorOptionScalar:
        if key in self.options:
            return self.options[key]
        for alias in aliases:
            if alias in self.options:
                return self.options[alias]
        return default

    def get_str_option(
        self,
        key: str,
        default: str = "",
        *,
        aliases: tuple[str, ...] = (),
    ) -> str:
        value = self.get_option(key, default, aliases=aliases)
        if value in (None, ""):
            return default
        return str(value)

    def get_int_option(
        self,
        key: str,
        default: int | None = None,
        *,
        aliases: tuple[str, ...] = (),
    ) -> int | None:
        value = self.get_option(key, default, aliases=aliases)
        if value is None or value == "":
            return default
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def get_bool_option(
        self,
        key: str,
        default: bool = False,
        *,
        aliases: tuple[str, ...] = (),
    ) -> bool:
        value = self.get_option(key, default, aliases=aliases)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    @staticmethod
    def _string_option(
        options: dict[str, ConnectorOptionScalar],
        key: str,
        *,
        aliases: tuple[str, ...] = (),
        default: str = "",
    ) -> str:
        if key in options and options[key] not in (None, ""):
            return str(options[key])
        for alias in aliases:
            if alias in options and options[alias] not in (None, ""):
                return str(options[alias])
        return default


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """Specification for a SQL query to execute."""

    sql: str
    connector_name: str = "default"
    timeout_override: int | None = None
    cost_limit_usd: float | None = None
    parameters: dict[str, object] = field(default_factory=dict)

    @property
    def effective_timeout(self) -> int:
        return self.timeout_override or 30


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated cost of a query."""

    estimated_bytes: int = 0
    estimated_cost_usd: float = 0.0
    estimated_rows: int = 0
    is_within_limit: bool = True
    message: str = ""


# ---------------------------------------------------------------------------
# SQL Safety Validator
# ---------------------------------------------------------------------------

# Patterns that indicate write/DDL/DCL operations
_UNSAFE_PATTERNS: list[tuple[str, str]] = [
    (r"\bCREATE\b", "DDL: CREATE"),
    (r"\bALTER\b", "DDL: ALTER"),
    (r"\bDROP\b", "DDL: DROP"),
    (r"\bTRUNCATE\b", "DDL: TRUNCATE"),
    (r"\bRENAME\b", "DDL: RENAME"),
    (r"\bINSERT\b", "DML: INSERT"),
    (r"\bUPDATE\b", "DML: UPDATE"),
    (r"\bDELETE\b", "DML: DELETE"),
    (r"\bMERGE\b", "DML: MERGE"),
    (r"\bGRANT\b", "DCL: GRANT"),
    (r"\bREVOKE\b", "DCL: REVOKE"),
]

# Allowed statement types
_ALLOWED_PREFIXES = frozenset({"SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE"})


@dataclass(frozen=True, slots=True)
class SqlValidationResult:
    """Result of SQL safety validation."""

    is_safe: bool
    violations: tuple[str, ...] = ()


def validate_sql_safety(sql: str) -> SqlValidationResult:
    """Validate that a SQL query is read-only (no DDL/DML/DCL).

    Returns a SqlValidationResult with is_safe=True for safe queries.
    """
    # Normalize: strip comments and whitespace
    cleaned = _strip_sql_comments(sql).strip()
    if not cleaned:
        return SqlValidationResult(is_safe=False, violations=("Empty query",))

    # Check first keyword is allowed
    first_word = cleaned.split()[0].upper()
    if first_word not in _ALLOWED_PREFIXES:
        return SqlValidationResult(
            is_safe=False,
            violations=(f"Query must start with SELECT/WITH/EXPLAIN, got: {first_word}",),
        )

    # Scan for unsafe patterns
    violations: list[str] = []
    upper_sql = cleaned.upper()
    for pattern, label in _UNSAFE_PATTERNS:
        if re.search(pattern, upper_sql) and not _is_in_string_literal(cleaned, pattern):
            violations.append(label)

    if violations:
        return SqlValidationResult(is_safe=False, violations=tuple(violations))

    return SqlValidationResult(is_safe=True)


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL comments (-- and /* */)."""
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", "", sql)
    # Remove multi-line comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql


def _is_in_string_literal(sql: str, pattern: str) -> bool:
    """Check if a pattern match is inside a string literal (rough heuristic)."""
    # Simple heuristic: count quotes before the match
    match = re.search(pattern, sql, re.IGNORECASE)
    if not match:
        return False
    before = sql[: match.start()]
    single_quotes = before.count("'") - before.count("\\'")
    return single_quotes % 2 == 1
