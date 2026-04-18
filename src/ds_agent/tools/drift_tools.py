"""Drift monitoring tools."""

from __future__ import annotations

import json

from ds_agent.application.services.drift_analyzer import DriftAnalyzer
from ds_agent.tools.registry import tool


@tool(
    name="drift_monitor",
    description=(
        "Compare a reference dataset to a current dataset and report feature-level drift "
        "using PSI, KL divergence, and KS statistics."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "reference_data": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
                "description": "Reference data as a list of records.",
            },
            "current_data": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
                "description": "Current data as a list of records.",
            },
            "reference_path": {
                "type": "string",
                "description": "Path to the reference dataset.",
            },
            "current_path": {
                "type": "string",
                "description": "Path to the current dataset.",
            },
            "features": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subset of features to check.",
            },
        },
    },
    prompt=(
        "Use drift_monitor when you need operational drift checks.\n"
        "- Pass in-memory records or file paths.\n"
        "- Review top_drifting_features and recommended_action before retraining."
    ),
)
async def drift_monitor(
    reference_data: list[dict] | None = None,
    current_data: list[dict] | None = None,
    reference_path: str | None = None,
    current_path: str | None = None,
    features: list[str] | None = None,
) -> str:
    reference = reference_data if reference_data is not None else reference_path
    current = current_data if current_data is not None else current_path
    if reference is None or current is None:
        return json.dumps({"error": "Provide either reference/current data or reference/current paths."})

    report = DriftAnalyzer().analyze(reference, current, features=features)
    return json.dumps(report.to_dict())
