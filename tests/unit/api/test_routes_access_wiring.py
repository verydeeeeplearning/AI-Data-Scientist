"""Wave 4 PLAN_05 — verify access dependencies are wired on mutation routes.

Picks five representative routes that landed in the bulk extension pass and
asserts that each declares an access dependency from
``ds_agent.api.dependencies.access``. The test treats the dependency callable
as opaque — it only checks that it originates from the access factory module —
because the per-route extractor lambdas are not stable identifiers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest
from fastapi.routing import APIRoute

from ds_agent.api.routes import (
    approval_grants,
    cards,
    certification,
    config,
    work_objects,
    workspace,
)


def _find_route(router: Any, path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


def _dependency_callables(route: APIRoute) -> Iterable[Any]:
    for sub in route.dependant.dependencies:
        if sub.call is not None:
            yield sub.call


def _has_access_dependency(route: APIRoute) -> bool:
    """The factory wraps the real check inside ``_dependency`` defined inside
    ``require_resource_access``, so the callable's module is access.py."""
    for call in _dependency_callables(route):
        module = getattr(call, "__module__", "")
        if module.endswith("api.dependencies.access"):
            return True
    return False


@pytest.mark.parametrize(
    ("module", "path", "method"),
    [
        (config, "/api/config", "POST"),
        (approval_grants, "/api/approval/grants/{grant_id}/revoke", "POST"),
        (cards, "/api/cards/{card_id}/pin", "POST"),
        (certification, "/api/certification/{mission_name}/submit", "POST"),
        (work_objects, "/api/work-objects/{work_object_id}/phase", "POST"),
        (workspace, "/api/workspace/upload", "POST"),
    ],
)
def test_mutation_route_declares_access_dependency(
    module: Any, path: str, method: str
) -> None:
    route = _find_route(module.router, path, method)
    assert _has_access_dependency(route), (
        f"{method} {path} is missing an access dependency"
    )


def test_read_only_route_has_no_access_dependency() -> None:
    """Sanity: GET endpoints must NOT pick up the mutation dependency."""
    route = _find_route(config.router, "/api/config", "GET")
    assert not _has_access_dependency(route)
