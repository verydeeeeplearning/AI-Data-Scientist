from io import StringIO

from rich.console import Console

from ds_agent.cli.mode_cli import run_mode_command
from ds_agent.config.schema import DSAgentConfig


class TestModeCli:
    def test_status_shows_effective_delegate_when_overlay_missing(self, tmp_path):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["status"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=DSAgentConfig(),
        )

        assert exit_code == 0
        output = out.getvalue()
        assert "Authority overlay:" in output
        assert "delegate" in output

    def test_incident_start_sets_overlay_and_started_at(self, tmp_path):
        config = DSAgentConfig()
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["incident", "start"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=config,
        )

        assert exit_code == 0
        assert config.gateway.authority_overlay == "incident"
        assert config.gateway.authority_overlay_started_at is not None

    def test_freeze_alias_start_sets_overlay(self, tmp_path):
        config = DSAgentConfig()
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["freeze"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=config,
        )

        assert exit_code == 0
        assert config.gateway.authority_overlay == "freeze"
        assert config.gateway.authority_overlay_started_at is None

    def test_overlay_end_clears_config(self, tmp_path):
        config = DSAgentConfig(
            gateway={
                "authority_overlay": "freeze",
            }
        )
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["freeze", "end"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=config,
        )

        assert exit_code == 0
        assert config.gateway.authority_overlay is None
        assert config.gateway.authority_overlay_started_at is None

    def test_migrate_preview_prints_exact_mapping_for_auto(self, tmp_path):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["migrate", "auto"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=DSAgentConfig(),
        )

        assert exit_code == 0
        output = out.getvalue()
        assert "Legacy mode migration preview" in output
        assert "Recommended authority:" in output
        assert "delegate" in output
        assert "peer_ds" in output
        assert "exact" in output

    def test_migrate_preview_warns_when_step_by_step_is_approximate(self, tmp_path):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        exit_code = run_mode_command(
            ["migrate", "step-by-step"],
            console=console,
            config_path=tmp_path / "config.yaml",
            config=DSAgentConfig(),
        )

        assert exit_code == 0
        output = out.getvalue()
        assert "approximate" in output
        assert "step-by-step" in output
        assert "supervised" in output
