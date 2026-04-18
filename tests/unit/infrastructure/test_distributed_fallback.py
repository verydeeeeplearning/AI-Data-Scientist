"""Distributed tool fallback tests for PLAN 17 Phase 6."""

from __future__ import annotations

import json

import pytest

from ds_agent.tools.distributed_tools import distributed_exec


class TestDistributedExecFallback:
    @pytest.mark.asyncio
    async def test_tool_returns_local_fallback_warning(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("value\n4\n5\n", encoding="utf-8")

        result = await distributed_exec(
            code="import pandas as pd\nprint(pd.read_csv(DATA_PATH)['value'].sum())",
            backend="dask",
            data_path=str(csv_path),
        )

        assert "fallback" in result.lower()
        assert "9" in result

    @pytest.mark.asyncio
    async def test_tool_rejects_unknown_backend(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("value\n1\n", encoding="utf-8")

        result = await distributed_exec(
            code="print('ok')",
            backend="spark",
            data_path=str(csv_path),
        )
        payload = json.loads(result)
        assert "error" in payload
