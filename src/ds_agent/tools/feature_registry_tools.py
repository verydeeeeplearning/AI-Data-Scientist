"""Feature registry tools for Decision OS orchestration."""

from __future__ import annotations

import json

from ds_agent.domain.errors.feature_registry_errors import FeatureRegistryError
from ds_agent.infrastructure.feature_registry_container import (
    FeatureRegistryContainer,
    build_feature_registry_container,
)
from ds_agent.tools.registry import tool

_container: FeatureRegistryContainer | None = None


def set_feature_registry_container(container: FeatureRegistryContainer) -> None:
    """Wire a feature-registry container into the tool module."""

    global _container
    _container = container


def _get_container() -> FeatureRegistryContainer:
    global _container
    if _container is not None:
        return _container

    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _container = build_feature_registry_container(str(workspace) if workspace is not None else None)
    return _container


def _ok_response(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _error_response(code: str, message: str, **payload: object) -> str:
    return json.dumps(
        {
            "ok": False,
            "error": {"code": code, "message": message},
            **payload,
        },
        ensure_ascii=False,
    )


def _handle_error(exc: Exception) -> str:
    if isinstance(exc, FeatureRegistryError):
        return _error_response(exc.error_code, str(exc))
    if isinstance(exc, ValueError):
        return _error_response("VALIDATION_ERROR", str(exc))
    return _error_response(type(exc).__name__.upper(), str(exc))


@tool(
    name="register_feature",
    description=(
        "Reads a feature YAML definition and registers it in the Decision OS "
        "feature registry with schema-catalog validation."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "yaml_uri": {"type": "string"},
        },
        "required": ["yaml_uri"],
    },
)
def register_feature(yaml_uri: str) -> str:
    try:
        result = _get_container().register.execute(yaml_uri)
        return _ok_response(**result.model_dump(mode="json"))
    except Exception as exc:
        return _handle_error(exc)
