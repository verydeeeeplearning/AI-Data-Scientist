"""Verified query store domain models."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ds_agent.memory.semantic.domain._normalization import normalize_string_list

QueryParameterType = Literal["date", "datetime", "int", "float", "string", "array"]
QueryDialect = Literal["postgres", "bigquery", "snowflake", "duckdb", "databricks_sql"]

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class QueryParameter(BaseModel):
    """One named parameter exposed by a verified query."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    type: QueryParameterType
    description: str = Field(min_length=1)
    default: str | None = None


class VerifiedQuery(BaseModel):
    """SQL template that was validated against a trusted source."""

    model_config = ConfigDict(frozen=True)

    vq_id: str = Field(min_length=1)
    metric_id: str | None = Field(default=None, min_length=1)
    dialect: QueryDialect
    description: str = Field(min_length=1)
    sql_template: str = Field(min_length=1)
    parameters: list[QueryParameter] = Field(default_factory=list)
    referenced_tables: list[str] = Field(default_factory=list)
    verified_by: str = Field(min_length=1)
    last_verified: date
    verification_evidence: str = Field(min_length=1)
    failure_modes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("referenced_tables", "failure_modes", "tags", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)

    @model_validator(mode="after")
    def _validate_parameters(self) -> VerifiedQuery:
        parameter_names = [param.name for param in self.parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("query parameter names must be unique")

        placeholders = set(_PLACEHOLDER_PATTERN.findall(self.sql_template))
        if placeholders != set(parameter_names):
            raise ValueError("sql_template placeholders must match parameter names")
        return self

