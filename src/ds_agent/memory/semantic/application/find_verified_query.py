"""Use case for resolving verified SQL templates."""

from __future__ import annotations

import re

from ds_agent.memory.semantic.application.dtos import VerifiedQueryResultDTO
from ds_agent.memory.semantic.application.ports import VerifiedQueryRepository
from ds_agent.memory.semantic.domain.verified_query import QueryDialect

_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class FindVerifiedQueryUseCase:
    """Locate and parameter-bind a verified query."""

    def __init__(self, queries: VerifiedQueryRepository) -> None:
        self._queries = queries

    def execute(
        self,
        metric_id: str,
        *,
        dialect: QueryDialect | None = None,
        bindings: dict[str, object] | None = None,
    ) -> VerifiedQueryResultDTO:
        matches = self._queries.find_by_metric(metric_id, dialect=dialect)
        if not matches:
            return VerifiedQueryResultDTO()

        query = matches[0]
        binding_map = {key: self._render_value(value) for key, value in (bindings or {}).items()}
        parameter_defaults = {
            parameter.name: parameter.default for parameter in query.parameters
        }
        rendered_sql = self._bind_sql(query.sql_template, binding_map, parameter_defaults)

        unresolved = _PLACEHOLDER_PATTERN.findall(rendered_sql)
        if unresolved:
            raise ValueError(f"unresolved placeholders remain: {', '.join(sorted(unresolved))}")

        return VerifiedQueryResultDTO(
            query=query,
            rendered_sql=rendered_sql,
            bound_parameters=binding_map,
        )

    @staticmethod
    def _render_value(value: object) -> str:
        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _bind_sql(
        sql_template: str,
        bindings: dict[str, str],
        parameter_defaults: dict[str, str | None],
    ) -> str:
        def replace(match: re.Match[str]) -> str:
            parameter_name = match.group(1)
            replacement = bindings.get(parameter_name)
            if replacement is None:
                replacement = parameter_defaults.get(parameter_name)
            if replacement is None:
                raise ValueError(f"missing required parameter: {parameter_name}")
            bindings[parameter_name] = replacement
            return replacement

        return _PLACEHOLDER_PATTERN.sub(replace, sql_template)
