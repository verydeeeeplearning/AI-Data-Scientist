"""Dashboard spec generation."""

from __future__ import annotations

import json


class DashboardSpecEngine:
    """Generate JSON or YAML dashboard specifications."""

    def build(
        self,
        *,
        metrics: list[dict[str, object]],
        dimensions: list[str] | None = None,
        filters: list[dict[str, object]] | None = None,
        layout: dict[str, object] | None = None,
        output_format: str = "json",
    ) -> str:
        payload = {
            "metrics": metrics,
            "dimensions": dimensions or [],
            "filters": filters or [],
            "layout": layout or {"type": "grid", "columns": 2},
        }
        if output_format == "json":
            return json.dumps(payload, indent=2)
        if output_format == "yaml":
            return self._to_yaml(payload)
        raise ValueError(f"Unsupported dashboard format: {output_format}")

    def _to_yaml(self, payload: dict[str, object]) -> str:
        lines: list[str] = []
        for key, value in payload.items():
            lines.extend(self._yaml_lines(key, value, indent=0))
        return "\n".join(lines) + "\n"

    def _yaml_lines(self, key: str, value: object, *, indent: int) -> list[str]:
        prefix = " " * indent
        if isinstance(value, dict):
            lines = [f"{prefix}{key}:"]
            for child_key, child_value in value.items():
                lines.extend(self._yaml_lines(str(child_key), child_value, indent=indent + 2))
            return lines
        if isinstance(value, list):
            lines = [f"{prefix}{key}:"]
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    for child_key, child_value in item.items():
                        lines.extend(
                            self._yaml_lines(str(child_key), child_value, indent=indent + 4)
                        )
                else:
                    lines.append(f"{prefix}  - {item}")
            return lines
        return [f"{prefix}{key}: {value}"]
