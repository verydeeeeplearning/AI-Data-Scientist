"""User-input sensor for runtime observability."""

from __future__ import annotations

from ds_agent.runtime.sensor_hub import SensorEvent, SensorHub


class UserInputSensor:
    """Publish foreground user input as sensor events."""

    def __init__(self, sensor_hub: SensorHub) -> None:
        self._hub = sensor_hub

    def record_message(
        self,
        *,
        session_id: str,
        surface: str,
        message: str,
        run_id: str | None = None,
    ) -> SensorEvent:
        """Publish one user message event."""
        metadata: dict[str, object] = {"dispatch": False}
        if run_id is not None:
            metadata["runId"] = run_id
        return self._hub.publish(
            sensor="user_input",
            kind="user.message",
            session_id=session_id,
            surface=surface,
            message=message,
            metadata=metadata,
        )
