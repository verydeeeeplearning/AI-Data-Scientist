"""Tests for api/__main__.py entry point."""

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")


class TestApiMain:
    def test_api_main_calls_app_main(self):
        """Importing __main__ triggers main() call."""
        with patch("ds_agent.api.app.main") as mock_main:
            import importlib

            import ds_agent.api.__main__ as mod

            importlib.reload(mod)
            # reload triggers one call; prior import may have called it too
            assert mock_main.call_count >= 1
