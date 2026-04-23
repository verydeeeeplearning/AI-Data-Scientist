"""YAML loader for autonomy mission packs."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from ds_agent.domain.entities.mission_pack import MissionPack

_MISSION_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class MissionPackLoader:
    """Load mission pack YAML files from the local mission registry."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self._root_dir = Path(root_dir) if root_dir is not None else _default_root_dir()

    def load(self, name: str) -> MissionPack:
        """Load one mission pack by slug name."""

        mission_name = _normalize_mission_name(name)
        return self.load_file(self._root_dir / f"{mission_name}.yaml")

    def try_load(self, name: str) -> MissionPack | None:
        """Load one mission pack or return ``None`` when unavailable/invalid."""

        try:
            return self.load(name)
        except ValueError:
            return None

    def load_file(self, path: str | Path) -> MissionPack:
        """Load one explicit YAML file inside the configured mission root."""

        root_dir = self._root_dir.expanduser().resolve()
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_relative_to(root_dir):
            raise ValueError(f"Mission pack path must stay inside {root_dir}.")

        try:
            payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Mission pack YAML must contain a mapping.")
            return MissionPack.model_validate(payload)
        except FileNotFoundError as exc:
            raise ValueError(f"Mission pack not found: {resolved}.") from exc
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid mission pack file {resolved}: {exc}") from exc

    def list_packs(self) -> list[str]:
        """Return available mission pack slugs."""

        if not self._root_dir.exists():
            return []
        return [path.stem for path in sorted(self._root_dir.glob("*.yaml"))]


def _default_root_dir() -> Path:
    return Path(__file__).resolve().parent / "missions"


def _normalize_mission_name(name: str) -> str:
    normalized = str(name).strip().lower()
    if not _MISSION_NAME_RE.fullmatch(normalized):
        raise ValueError(f"Invalid mission pack name: {name!r}")
    return normalized
