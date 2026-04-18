"""Distributed adapter tests for PLAN 17 Phase 6."""

from __future__ import annotations

import pytest

from ds_agent.infrastructure.distributed.dask_adapter import DaskAdapter


class TestDaskAdapter:
    @pytest.mark.asyncio
    async def test_falls_back_to_local_pandas_when_dask_missing(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("value\n1\n2\n3\n", encoding="utf-8")

        adapter = DaskAdapter()
        result = await adapter.execute(
            "import pandas as pd\nprint(pd.read_csv(DATA_PATH)['value'].sum())",
            str(csv_path),
        )

        assert "6" in result
        assert "fallback" in result.lower()
