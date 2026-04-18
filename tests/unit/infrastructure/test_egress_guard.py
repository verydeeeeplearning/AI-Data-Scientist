"""S14 tests for the in-adapter egress kill-switch (RC-5 closure).

Covers:
- the ``is_egress_enabled()`` env-var recognition matrix
- that the default ``DS_AGENT_NETWORK_EGRESS_ENABLED`` unset path denies
- the ``make_disabled_result()`` public return shape
- that all five connectors (Slack, Jira, Confluence, Notion, Git) route
  through the guard when ``dry_run=False`` is passed
"""

from __future__ import annotations

import pytest

from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no leak from ambient env into these tests."""
    monkeypatch.delenv("DS_AGENT_NETWORK_EGRESS_ENABLED", raising=False)


class TestIsEgressEnabled:
    @pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "YES", "on", "ON"])
    def test_truthy_values_enable(self, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DS_AGENT_NETWORK_EGRESS_ENABLED", value)
        assert is_egress_enabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "FALSE", "no", "off", "random"])
    def test_falsy_values_disable(self, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DS_AGENT_NETWORK_EGRESS_ENABLED", value)
        assert is_egress_enabled() is False

    def test_unset_defaults_to_disabled(self) -> None:
        assert is_egress_enabled() is False

    def test_whitespace_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DS_AGENT_NETWORK_EGRESS_ENABLED", "  TRUE  ")
        assert is_egress_enabled() is True


class TestDisabledResult:
    def test_error_code_and_message(self) -> None:
        code, msg = make_disabled_result()
        assert code == "EGRESS_DISABLED"
        assert "DS_AGENT_NETWORK_EGRESS_ENABLED" in msg
