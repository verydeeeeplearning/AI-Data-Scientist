"""Distributed execution tool."""

from __future__ import annotations

import json

from ds_agent.infrastructure.distributed.dask_adapter import DaskAdapter
from ds_agent.infrastructure.distributed.ray_adapter import RayAdapter
from ds_agent.tools.registry import tool


@tool(
    name="distributed_exec",
    description=(
        "Execute DS code with a distributed backend such as Dask or Ray, "
        "with graceful fallback to local pandas when the backend is unavailable."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. DATA_PATH is injected automatically.",
            },
            "backend": {
                "type": "string",
                "enum": ["dask", "ray", "spark"],
                "description": "Distributed execution backend.",
            },
            "data_path": {
                "type": "string",
                "description": "Dataset path exposed to the code as DATA_PATH.",
            },
            "timeout": {
                "type": "integer",
                "default": 120,
                "description": "Execution timeout in seconds.",
            },
        },
        "required": ["code", "backend", "data_path"],
    },
    timeout=300,
    prompt=(
        "Use distributed_exec when data is too large for direct local processing.\n"
        "- DATA_PATH is injected into the sandbox.\n"
        "- Prefer Dask for dataframe-style workloads and Ray for parallel sweeps."
    ),
    safety_level="caution",
)
async def distributed_exec(
    code: str,
    backend: str,
    data_path: str,
    timeout: int = 120,
) -> str:
    if backend == "dask":
        return await DaskAdapter(timeout=timeout).execute(code, data_path)
    if backend == "ray":
        return await RayAdapter(timeout=timeout).execute(code, data_path)
    return json.dumps({"error": f"Unsupported distributed backend: {backend}"})
