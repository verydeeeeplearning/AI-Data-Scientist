"""Decision OS post-deploy status use cases."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from ds_agent.application.dtos.post_deploy import PostDeployStatusResultDTO
from ds_agent.application.ports.post_deploy_support import DeployMonitorStateStore

_WINDOW_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class GetPostDeployStatusUseCase:
    """Query recent post-deploy monitoring state for one model."""

    def __init__(self, states: DeployMonitorStateStore) -> None:
        self._states = states

    def execute(self, model_id: str, window: str = "7d") -> PostDeployStatusResultDTO:
        since = datetime.now(UTC) - _parse_window(window)
        states = self._states.list_states(model_id=model_id, since=since, limit=100)
        if not states:
            raise LookupError(f"No post-deploy status found for model: {model_id}")

        latest = states[0]
        alerts: list[str] = []
        seen: set[str] = set()
        for state in states:
            for alert in state.alerts:
                if alert in seen:
                    continue
                seen.add(alert)
                alerts.append(alert)
        return PostDeployStatusResultDTO(
            model_id=model_id,
            model_version=latest.model_version,
            window=window,
            summary=latest,
            alerts=alerts,
            observations=len(states),
        )


def _parse_window(window: str) -> timedelta:
    match = _WINDOW_PATTERN.fullmatch(window.strip())
    if match is None:
        raise ValueError(f"Unsupported window: {window}")
    value = int(match.group("value"))
    unit = match.group("unit")
    return timedelta(seconds=value * _UNIT_SECONDS[unit])
