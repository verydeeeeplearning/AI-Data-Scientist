"""Tests for cli/wizard/onboard.py (Phase 7)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from ds_agent.cli.wizard.onboard import (
    _ask_yn,
    _detect_existing_auth,
    _finish_message,
    _save_and_finish,
)


class TestDetectExistingAuth:
    def test_detect_codex(self, tmp_path):
        import json

        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        auth_file = codex_dir / "auth.json"
        auth_file.write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "t"}}))

        with patch("ds_agent.cli.wizard.onboard.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            result = _detect_existing_auth()

        assert result is not None
        assert "Codex" in result[0]

    def test_detect_anthropic_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        # Ensure no codex auth
        with patch("ds_agent.cli.wizard.onboard.Path") as mock_path:
            mock_codex = MagicMock()
            mock_codex.exists.return_value = False
            mock_div = MagicMock(__truediv__=MagicMock(return_value=mock_codex))
            mock_path.home.return_value.__truediv__ = MagicMock(return_value=mock_div)
            result = _detect_existing_auth()

        assert result is not None
        assert "Anthropic" in result[0]

    def test_detect_none(self, monkeypatch):
        # Remove all relevant env vars
        for var in [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "MISTRAL_API_KEY",
            "OPENROUTER_API_KEY",
        ]:
            monkeypatch.delenv(var, raising=False)

        with patch("ds_agent.cli.wizard.onboard.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_div = MagicMock(__truediv__=MagicMock(return_value=mock_file))
            mock_path.home.return_value.__truediv__ = MagicMock(
                return_value=mock_div,
            )
            result = _detect_existing_auth()

        assert result is None


class TestAskYn:
    def test_default_yes(self):
        console = Console(file=StringIO())
        console.input = MagicMock(return_value="")
        assert _ask_yn(console, "Question?", default=True) is True

    def test_default_no(self):
        console = Console(file=StringIO())
        console.input = MagicMock(return_value="")
        assert _ask_yn(console, "Question?", default=False) is False

    def test_explicit_yes(self):
        console = Console(file=StringIO())
        for answer in ["y", "yes", "ㅇ", "네"]:
            console.input = MagicMock(return_value=answer)
            assert _ask_yn(console, "Q?") is True

    def test_explicit_no(self):
        console = Console(file=StringIO())
        for answer in ["n", "no"]:
            console.input = MagicMock(return_value=answer)
            assert _ask_yn(console, "Q?") is False


class TestSaveAndFinish:
    def test_saves_config(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)

        with patch("ds_agent.cli.wizard.onboard.save_config") as mock_save:
            _save_and_finish(console, "anthropic/claude-sonnet-4-6")

        mock_save.assert_called_once()
        output = out.getvalue()
        assert len(output) > 0


class TestFinishMessage:
    def test_renders_model_in_output(self):
        out = StringIO()
        console = Console(file=out, force_terminal=True, width=120)
        _finish_message(console, "gpt-5.4", "/tmp/config.yaml")
        output = out.getvalue()
        assert "gpt-5.4" in output
