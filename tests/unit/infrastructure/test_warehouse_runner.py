"""Warehouse runner sandbox tests."""

from __future__ import annotations

import pytest


class TestWarehouseRunnerSandbox:
    @pytest.mark.asyncio
    async def test_denies_requests_import(self) -> None:
        from ds_agent.tools.warehouse_sandbox import WarehouseRunnerSandbox

        sandbox = WarehouseRunnerSandbox(timeout=5)
        result = await sandbox.execute("import requests\nprint('bad')")

        assert result.success is False
        assert "requests" in result.stderr.lower()
        assert "security check failed" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_allows_stdlib_code(self) -> None:
        from ds_agent.tools.warehouse_sandbox import WarehouseRunnerSandbox

        sandbox = WarehouseRunnerSandbox(timeout=5)
        result = sandbox._security.check("import json\nprint(json.dumps({'ok': True}))")

        assert result.allowed is True
        assert result.blocked_patterns == []
