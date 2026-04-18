"""Support bundle exporter for productized diagnostics."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import yaml

from ds_agent.config.loader import get_default_config_path
from ds_agent.config.schema import DSAgentConfig
from ds_agent.runtime.transcript_store import get_runtime_storage_root

_REDACTED = "***REDACTED***"
_MAX_TEXT_CHARS = 200_000
_MAX_SUMMARY_FILES = 50
_SECRET_KEYWORDS = ("key", "token", "secret", "password", "cookie", "auth")
_SECRET_PATTERNS = (
    re.compile(r"READY:(\d+):[^\s]+"),
    re.compile(r"sk-ant-[A-Za-z0-9\-_]+"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"ya29\.[A-Za-z0-9\-_]+"),
    re.compile(r"1//[A-Za-z0-9\-_]+"),
    re.compile(r"\b\d{8,}:[A-Za-z0-9\-_]{20,}\b"),
)


class SupportBundleExporter:
    """Export a redacted support bundle ZIP for diagnostics."""

    def __init__(
        self,
        *,
        config: DSAgentConfig,
        safe_config: dict[str, Any],
        status_snapshot: dict[str, Any] | None = None,
        config_path: str | Path | None = None,
    ) -> None:
        self._config = config
        self._safe_config = self._deep_redact(safe_config)
        self._status_snapshot = self._deep_redact(status_snapshot or {})
        self._config_path = (
            Path(config_path).expanduser().resolve()
            if config_path is not None
            else get_default_config_path().expanduser().resolve()
        )
        self._workspace_dir = Path(config.agent.workspace_dir).expanduser().resolve()
        self._runtime_root = get_runtime_storage_root(config.agent.workspace_dir).resolve()

    def export(self, output_path: str | Path) -> Path:
        """Write a support bundle ZIP to the requested path."""
        destination = Path(output_path).expanduser()
        if destination.exists() and destination.is_dir():
            destination = destination / self._default_bundle_name()
        if destination.suffix.lower() != ".zip":
            destination = destination.with_suffix(".zip")
        destination.parent.mkdir(parents=True, exist_ok=True)

        temp_root = Path(tempfile.mkdtemp(prefix="ds-agent-support-"))
        bundle_root = temp_root / destination.stem
        bundle_root.mkdir(parents=True, exist_ok=True)
        try:
            self._write_json(bundle_root / "manifest.json", self._build_manifest())
            self._write_json(bundle_root / "system_info.json", self._build_system_info())
            self._write_json(bundle_root / "version.json", self._build_version_info())
            self._write_json(bundle_root / "status.json", self._status_snapshot)
            self._write_yaml(bundle_root / "config.yaml", self._safe_config)
            self._write_json(bundle_root / "migration_state.json", self._build_migration_state())
            self._write_json(
                bundle_root / "runtime" / "snapshot.json",
                self._build_runtime_snapshot(),
            )

            self._copy_redacted_file(
                self._runtime_root / "audit_log.jsonl",
                bundle_root / "logs" / "audit_log.jsonl",
            )
            self._copy_redacted_file(
                self._runtime_root / "runtime-events.jsonl",
                bundle_root / "logs" / "runtime-events.jsonl",
            )
            self._copy_redacted_file(
                self._runtime_root / "organization.json",
                bundle_root / "runtime" / "organization.json",
            )

            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path in sorted(bundle_root.rglob("*")):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(bundle_root))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

        return destination.resolve()

    def _build_manifest(self) -> dict[str, Any]:
        return {
            "bundleVersion": 1,
            "generatedAt": time.time(),
            "workspaceDir": str(self._workspace_dir),
            "runtimeRoot": str(self._runtime_root),
        }

    def _build_system_info(self) -> dict[str, Any]:
        return {
            "os": platform.system(),
            "osVersion": platform.version(),
            "platform": platform.platform(),
            "pythonVersion": platform.python_version(),
            "arch": platform.machine(),
            "cpuCount": os.cpu_count(),
            "hostname": self._redact_text(platform.node()),
            "cwd": str(Path.cwd()),
        }

    def _build_version_info(self) -> dict[str, Any]:
        return {
            "appVersion": self._package_version(),
            "defaultModel": self._config.provider.default_model,
            "mode": self._config.agent.mode,
            "gatewayAutomationProfile": self._config.gateway.automation_profile,
        }

    def _build_migration_state(self) -> dict[str, Any]:
        migration_backup_dir = self._config_path.parent / ".migration-backups"
        backup_candidates = sorted(
            [path.name for path in self._config_path.parent.glob(f"{self._config_path.name}*.bak*")]
            + [path.name for path in migration_backup_dir.glob("config_v*_*.yaml")]
        )
        return {
            "configPath": str(self._config_path),
            "configExists": self._config_path.exists(),
            "backupCandidates": backup_candidates,
            "currentConfigVersion": (
                self._safe_config.get("schema_version") or self._safe_config.get("_schema_version")
            ),
        }

    def _build_runtime_snapshot(self) -> dict[str, Any]:
        return {
            "runtimeRootExists": self._runtime_root.exists(),
            "runtimeEntries": self._list_directory_entries(self._runtime_root),
            "workspaceEntries": self._list_workspace_entries(),
            "transcriptCount": self._count_matching_files(
                self._runtime_root / "transcripts",
                "*.json",
            ),
            "checkpointCount": self._count_matching_files(
                self._runtime_root / "checkpoints",
                "*.checkpoint.json",
            ),
        }

    def _list_workspace_entries(self) -> list[dict[str, Any]]:
        if not self._workspace_dir.exists():
            return []
        entries: list[dict[str, Any]] = []
        for path in sorted(self._workspace_dir.rglob("*")):
            if len(entries) >= _MAX_SUMMARY_FILES:
                break
            relative = path.relative_to(self._workspace_dir)
            if relative.parts and relative.parts[0] == ".ds-agent":
                continue
            entries.append(
                {
                    "path": relative.as_posix(),
                    "kind": "dir" if path.is_dir() else "file",
                }
            )
        return entries

    @staticmethod
    def _count_matching_files(directory: Path, pattern: str) -> int:
        if not directory.exists():
            return 0
        return sum(1 for _ in directory.glob(pattern))

    @staticmethod
    def _list_directory_entries(directory: Path) -> list[dict[str, Any]]:
        if not directory.exists():
            return []
        entries: list[dict[str, Any]] = []
        for path in sorted(directory.iterdir())[:_MAX_SUMMARY_FILES]:
            entries.append(
                {
                    "name": path.name,
                    "kind": "dir" if path.is_dir() else "file",
                }
            )
        return entries

    def _copy_redacted_file(self, source: Path, destination: Path) -> None:
        if not source.exists() or not source.is_file():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8", errors="replace")[:_MAX_TEXT_CHARS]
        if source.suffix == ".jsonl":
            sanitized_lines = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    sanitized_lines.append(self._redact_text(line))
                    continue
                sanitized_lines.append(json.dumps(self._deep_redact(payload), ensure_ascii=False))
            destination.write_text("\n".join(sanitized_lines) + "\n", encoding="utf-8")
            return

        if source.suffix == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                destination.write_text(self._redact_text(text), encoding="utf-8")
                return
            self._write_json(destination, self._deep_redact(payload))
            return

        destination.write_text(self._redact_text(text), encoding="utf-8")

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _write_yaml(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )

    @staticmethod
    def _default_bundle_name() -> str:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"ds-agent-support-{timestamp}.zip"

    @staticmethod
    def _package_version() -> str:
        try:
            return importlib.metadata.version("ds-agent")
        except importlib.metadata.PackageNotFoundError:
            return "0.1.0"

    def _deep_redact(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact_text(value)
        if isinstance(value, list):
            return [self._deep_redact(item) for item in value]
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                if any(keyword in key.lower() for keyword in _SECRET_KEYWORDS):
                    redacted[key] = _REDACTED
                    continue
                redacted[key] = self._deep_redact(item)
            return redacted
        return value

    def _redact_text(self, text: str) -> str:
        sanitized = text
        for pattern in _SECRET_PATTERNS:
            sanitized = pattern.sub(self._replace_secret_match, sanitized)
        return sanitized

    @staticmethod
    def _replace_secret_match(match: re.Match[str]) -> str:
        full_match = match.group(0)
        if full_match.startswith("READY:"):
            return f"READY:{match.group(1)}:{_REDACTED}"
        return _REDACTED
