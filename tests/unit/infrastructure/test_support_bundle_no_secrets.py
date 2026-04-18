from __future__ import annotations

import json
import zipfile
from pathlib import Path

from ds_agent.config.schema import AgentConfig, DSAgentConfig
from ds_agent.infrastructure.support.bundle_exporter import SupportBundleExporter
from ds_agent.runtime.transcript_store import get_runtime_storage_root


def test_support_bundle_redacts_secrets_and_includes_runtime_context(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "visible.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    hidden_runtime_file = workspace / ".ds-agent" / "internal.txt"
    hidden_runtime_file.parent.mkdir(parents=True)
    hidden_runtime_file.write_text("do not include", encoding="utf-8")

    config = DSAgentConfig(agent=AgentConfig(workspace_dir=str(workspace)))
    config_path = tmp_path / "config.yaml"
    config_path.write_text("version: 3\n", encoding="utf-8")

    runtime_root = get_runtime_storage_root(str(workspace))
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "audit_log.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "post_tool_use",
                        "session_id": "session-1",
                        "tool": "web_search",
                        "apiToken": "sk-ant-live-secretvalue",
                        "message": "READY:18790:super-secret-ready-token",
                    }
                ),
                json.dumps(
                    {
                        "event": "operator.alert",
                        "access_token": "ya29.super-secret-google-token",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime_root / "runtime-events.jsonl").write_text(
        json.dumps(
            {
                "kind": "runtime.bundle_test",
                "detail": "sk-abcdef1234567890SECRET",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runtime_root / "organization.json").write_text(
        json.dumps(
            {
                "name": "Acme Team",
                "botToken": "12345678:telegram-bot-secret-token",
                "members": [
                    {
                        "memberId": "admin",
                        "role": "admin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exporter = SupportBundleExporter(
        config=config,
        safe_config={
            "provider": {
                "default_model": "anthropic/claude-sonnet-4-6",
                "api_key": "sk-ant-live-secretvalue",
            },
            "channels": {
                "telegram": {
                    "bot_token": "12345678:telegram-bot-secret-token",
                }
            },
        },
        status_snapshot={
            "authToken": "oauth-secret-token",
            "status": "ok",
        },
        config_path=config_path,
    )

    bundle_path = exporter.export(tmp_path / "exports" / "support-bundle.zip")

    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "config.yaml" in names
        assert "system_info.json" in names
        assert "version.json" in names
        assert "status.json" in names
        assert "migration_state.json" in names
        assert "runtime/snapshot.json" in names
        assert "logs/audit_log.jsonl" in names
        assert "logs/runtime-events.jsonl" in names
        assert "runtime/organization.json" in names

        config_yaml = archive.read("config.yaml").decode("utf-8")
        assert "sk-ant-live-secretvalue" not in config_yaml
        assert "telegram-bot-secret-token" not in config_yaml
        assert "***REDACTED***" in config_yaml

        status_json = json.loads(archive.read("status.json").decode("utf-8"))
        assert status_json["authToken"] == "***REDACTED***"

        audit_log = archive.read("logs/audit_log.jsonl").decode("utf-8")
        assert "sk-ant-live-secretvalue" not in audit_log
        assert "ya29.super-secret-google-token" not in audit_log
        assert "super-secret-ready-token" not in audit_log
        assert "READY:18790:***REDACTED***" in audit_log

        runtime_events = archive.read("logs/runtime-events.jsonl").decode("utf-8")
        assert "sk-abcdef1234567890SECRET" not in runtime_events
        assert "***REDACTED***" in runtime_events

        organization = json.loads(archive.read("runtime/organization.json").decode("utf-8"))
        assert organization["botToken"] == "***REDACTED***"

        snapshot = json.loads(archive.read("runtime/snapshot.json").decode("utf-8"))
        workspace_paths = {entry["path"] for entry in snapshot["workspaceEntries"]}
        assert "visible.csv" in workspace_paths
        assert ".ds-agent/internal.txt" not in workspace_paths
