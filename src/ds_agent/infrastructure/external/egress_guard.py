"""In-adapter egress kill-switch (S14, closes RC-5).

Defense-in-depth: even if the upper-layer policy gate in IntegrationHub /
DeliveryRouter is misconfigured, no external connector will initiate real
network egress unless ``DS_AGENT_NETWORK_EGRESS_ENABLED`` is explicitly
set to a truthy value.

Default is **disabled** — operators must opt-in. This preserves the
product axiom that only hard constraints are enforced in code (see
memory ``feedback_preserve_autonomy`` §"Hard constraint만 코드가 강제").

See ``Docs/rfc/RFC_2026-04_adapter_killswitch.md`` for rationale and
alternatives.
"""

from __future__ import annotations

import os

_ENV_VAR = "DS_AGENT_NETWORK_EGRESS_ENABLED"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def is_egress_enabled() -> bool:
    """Return True only if the env var is set to a truthy value.

    Recognised truthy values (case-insensitive): ``1``, ``true``, ``yes``, ``on``.
    All other values (including unset, empty string, ``0``, ``false``) return
    False so that the fail-safe default denies egress.
    """
    value = os.environ.get(_ENV_VAR, "").strip().lower()
    return value in _TRUTHY


def make_disabled_result() -> tuple[str, str]:
    """Return the (error_code, error_message) tuple that connectors emit
    when egress is disabled.

    Callers wrap this in their connector-specific ``ConnectorResult``.
    """
    return (
        "EGRESS_DISABLED",
        f"Network egress disabled at adapter layer. "
        f"Set {_ENV_VAR}=true to enable.",
    )
