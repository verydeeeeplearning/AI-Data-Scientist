"""Shared helpers for verifier infrastructure adapters."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult

_STATUS_PRIORITY: dict[str, int] = {
    "error": 4,
    "fail": 3,
    "warn": 2,
    "pass": 1,
    "skipped": 0,
}


def coerce_frame(data: object | None) -> pd.DataFrame | None:
    """Convert verifier artifact payloads into a DataFrame when possible."""

    if data is None:
        return None
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if isinstance(data, (str, Path)):
        path = Path(data)
        suffix = path.suffix.lower()
        if suffix in {".parquet", ".pq"}:
            return pd.read_parquet(path)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        if suffix == ".json":
            return pd.read_json(path)
        return pd.read_csv(path)
    if isinstance(data, Mapping):
        return pd.DataFrame(data)
    return pd.DataFrame(data)


def artifact(ctx: VerifierContext, *keys: str, default: Any = None) -> Any:
    """Return the first present artifact value from a list of candidate keys."""

    for key in keys:
        if key in ctx.artifacts:
            return ctx.artifacts[key]
    return default


def elapsed_ms(start: float) -> int:
    """Convert a perf_counter start time into elapsed milliseconds."""

    return int((perf_counter() - start) * 1000)


def safe_run_check(
    ctx: VerifierContext,
    check: Any,
) -> CheckResult:
    """Execute one check and normalize unexpected failures."""

    try:
        result: CheckResult = check.run(ctx)
        return result
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return CheckResult(
            check_id=getattr(check, "name", check.__class__.__name__.lower()),
            status="error",
            score=0.0,
            evidence={"exception_type": type(exc).__name__},
            message=str(exc),
            duration_ms=0,
        )


def aggregate_layer(
    *,
    layer: Any,
    checks: Sequence[CheckResult],
    weights: Mapping[str, float] | None = None,
) -> LayerResult:
    """Build a LayerResult from deterministic check outputs."""

    weight_map = dict(weights or {})
    worst_status = "pass"
    total_weight = 0.0
    total_score = 0.0
    error_count = 0

    for check in checks:
        if _STATUS_PRIORITY[check.status] > _STATUS_PRIORITY[worst_status]:
            worst_status = check.status
        if check.status == "error":
            error_count += 1
        if check.status in {"skipped", "error"}:
            continue
        weight = weight_map.get(check.check_id, 1.0)
        total_weight += weight
        total_score += check.score * weight

    score = (total_score / total_weight) if total_weight > 0 else 1.0
    summary = _summarize_checks(checks)
    overall_status: Any = "error" if worst_status == "error" else worst_status
    return LayerResult(
        layer=layer,
        overall=overall_status,
        checks=list(checks),
        score=score,
        summary=summary,
        partial_failure=error_count > (len(checks) / 2),
    )


def metric_from_predictions(
    frame: pd.DataFrame,
    *,
    truth_column: str,
    prediction_column: str,
) -> float:
    """Compute simple accuracy from truth/prediction columns."""

    valid = frame[[truth_column, prediction_column]].dropna()
    if valid.empty:
        return 0.0
    return float((valid[truth_column] == valid[prediction_column]).mean())


def numeric_columns(frame: pd.DataFrame, *, exclude: Iterable[str] = ()) -> list[str]:
    """Return numeric columns excluding user-specified names."""

    excluded = set(exclude)
    return [
        column
        for column in frame.columns
        if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
    ]


def _summarize_checks(checks: Sequence[CheckResult]) -> str:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0, "error": 0}
    for check in checks:
        counts[check.status] += 1
    return (
        f"pass={counts['pass']} warn={counts['warn']} fail={counts['fail']} "
        f"skipped={counts['skipped']} error={counts['error']}"
    )
