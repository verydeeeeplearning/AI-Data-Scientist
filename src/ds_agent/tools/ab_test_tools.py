"""A/B test tools."""

from __future__ import annotations

import json

from ds_agent.application.services.ab_test_analyzer import ABTestAnalyzer
from ds_agent.tools.registry import tool


@tool(
    name="ab_test",
    description=(
        "Design, validate, and analyze A/B tests with power analysis, SRM checks, "
        "significance tests, and sequential testing."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["design", "check", "analyze"],
                "description": "Which A/B testing action to run.",
            },
            "effect_size": {"type": "number"},
            "alpha": {"type": "number", "default": 0.05},
            "power": {"type": "number", "default": 0.8},
            "test_type": {"type": "string", "default": "proportion"},
            "control_n": {"type": "integer"},
            "treatment_n": {"type": "integer"},
            "expected_control_ratio": {"type": "number", "default": 0.5},
            "expected_treatment_ratio": {"type": "number", "default": 0.5},
            "control_values": {"type": "array", "items": {"type": "number"}},
            "treatment_values": {"type": "array", "items": {"type": "number"}},
            "metric_type": {"type": "string", "default": "continuous"},
            "p_value": {"type": "number"},
            "look": {"type": "integer", "default": 1},
            "max_looks": {"type": "integer", "default": 3},
        },
        "required": ["action"],
    },
    prompt=(
        "Use ab_test for experiment design and readouts.\n"
        "- design: power analysis\n"
        "- check: SRM and sequential checks\n"
        "- analyze: significance and treatment effect summary"
    ),
)
async def ab_test(
    action: str,
    effect_size: float | None = None,
    alpha: float = 0.05,
    power: float = 0.8,
    test_type: str = "proportion",
    control_n: int | None = None,
    treatment_n: int | None = None,
    expected_control_ratio: float = 0.5,
    expected_treatment_ratio: float = 0.5,
    control_values: list[float] | None = None,
    treatment_values: list[float] | None = None,
    metric_type: str = "continuous",
    p_value: float | None = None,
    look: int = 1,
    max_looks: int = 3,
) -> str:
    analyzer = ABTestAnalyzer()

    if action == "design":
        if effect_size is None:
            return json.dumps({"error": "effect_size is required for action='design'"})
        return json.dumps(
            analyzer.power_analysis(
                effect_size=effect_size,
                alpha=alpha,
                power=power,
                test_type=test_type,
            ).to_dict()
        )

    if action == "check":
        if control_n is None or treatment_n is None:
            return json.dumps({"error": "control_n and treatment_n are required for action='check'"})
        payload: dict[str, object] = {
            "srm": analyzer.srm_check(
                control_n=control_n,
                treatment_n=treatment_n,
                expected_ratio=(expected_control_ratio, expected_treatment_ratio),
            ).to_dict()
        }
        if p_value is not None:
            payload["sequential"] = analyzer.sequential_test(
                p_value=p_value,
                look=look,
                max_looks=max_looks,
                alpha=alpha,
            ).to_dict()
        return json.dumps(payload)

    if action == "analyze":
        if control_values is None or treatment_values is None:
            return json.dumps(
                {"error": "control_values and treatment_values are required for action='analyze'"}
            )
        payload = analyzer.analyze(
            control_values, treatment_values, metric_type=metric_type
        ).to_dict()
        if control_n is not None and treatment_n is not None:
            payload["srm"] = analyzer.srm_check(
                control_n=control_n,
                treatment_n=treatment_n,
                expected_ratio=(expected_control_ratio, expected_treatment_ratio),
            ).to_dict()
        return json.dumps(payload)

    return json.dumps({"error": f"Unsupported action: {action}"})
