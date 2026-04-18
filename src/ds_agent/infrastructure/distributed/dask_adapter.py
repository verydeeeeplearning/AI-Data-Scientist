"""Dask-backed distributed execution with graceful fallback."""

from __future__ import annotations

import importlib.util
import json

from ds_agent.application.services.execution_router import ExecutionRouter
from ds_agent.tools.path_utils import get_active_workspace
from ds_agent.tools.sandbox import create_secure_sandbox


class DaskAdapter:
    """Execute code with Dask when available, otherwise fall back to pandas."""

    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout

    def is_available(self) -> bool:
        return importlib.util.find_spec("dask") is not None

    async def execute(self, code: str, data_path: str) -> str:
        active_backend = "dask" if self.is_available() else "pandas"
        warning = (
            ""
            if active_backend == "dask"
            else "Dask unavailable. Running local pandas fallback. Large datasets may OOM."
        )
        preamble = (
            f"DATA_PATH = {data_path!r}\n"
            f"ACTIVE_BACKEND = {active_backend!r}\n"
            "from pathlib import Path\n"
            "import pandas as pd\n"
            "def read_frame(path: str = DATA_PATH):\n"
            "    suffix = Path(path).suffix.lower()\n"
            "    if ACTIVE_BACKEND == 'dask':\n"
            "        import dask.dataframe as dd\n"
            "        if suffix in {'.parquet', '.pq'}:\n"
            "            return dd.read_parquet(path)\n"
            "        return dd.read_csv(path)\n"
            "    if suffix in {'.parquet', '.pq'}:\n"
            "        return pd.read_parquet(path)\n"
            "    return pd.read_csv(path)\n"
        )
        workspace = get_active_workspace()
        sandbox = create_secure_sandbox(
            timeout=self._timeout,
            working_dir=str(workspace) if workspace else None,
            policy=ExecutionRouter().policy_for_tool("distributed_exec"),
        )
        result = await sandbox.execute(preamble + code)
        if not result.success:
            return json.dumps({"error": result.stderr, "backend": "dask"})
        output = result.stdout or "distributed execution completed."
        if warning:
            return f"WARNING: {warning}\n{output}"
        return output
