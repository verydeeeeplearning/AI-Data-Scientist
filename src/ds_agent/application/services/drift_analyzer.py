"""Drift analysis services for PLAN 17 Phase 5."""

from __future__ import annotations

import csv
import json
import math
from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from ds_agent.domain.value_objects.drift import DriftMetric, DriftReport

_PANDAS_FRAME_MODULE = "pandas"
_SUPPORTED_PANDAS_SUFFIXES = frozenset({".parquet", ".pq", ".xlsx", ".xls"})


class DriftAnalyzer:
    """Compute drift metrics between reference and current datasets."""

    def __init__(
        self,
        warning_threshold: float = 0.1,
        danger_threshold: float = 0.2,
        smoothing: float = 1e-6,
        bins: int = 10,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._danger_threshold = danger_threshold
        self._smoothing = smoothing
        self._bins = bins

    def calculate_psi(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        bins: int | None = None,
    ) -> float:
        """Population Stability Index."""
        ref_dist, cur_dist = self._to_distribution(reference, current, bins=bins)
        return sum(
            (ref - cur) * math.log(ref / cur) for ref, cur in zip(ref_dist, cur_dist, strict=True)
        )

    def calculate_kl_divergence(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        bins: int | None = None,
    ) -> float:
        """KL divergence from reference to current."""
        ref_dist, cur_dist = self._to_distribution(reference, current, bins=bins)
        return sum(ref * math.log(ref / cur) for ref, cur in zip(ref_dist, cur_dist, strict=True))

    def calculate_ks_test(
        self,
        reference: Sequence[float],
        current: Sequence[float],
    ) -> dict[str, float]:
        """KS statistic and asymptotic p-value."""
        ref = sorted(self._as_float_values(reference))
        cur = sorted(self._as_float_values(current))
        if not ref or not cur:
            return {"statistic": 0.0, "p_value": 1.0}

        statistic = self._ks_statistic(ref, cur)
        p_value = self._ks_p_value(statistic, len(ref), len(cur))
        return {"statistic": statistic, "p_value": p_value}

    def analyze(
        self,
        reference_data: object,
        current_data: object,
        features: Iterable[str] | None = None,
    ) -> DriftReport:
        """Analyze drift feature by feature."""
        reference_frame = self._coerce_frame(reference_data)
        current_frame = self._coerce_frame(current_data)

        if features is None:
            shared = set(reference_frame) & set(current_frame)
            selected = [
                column
                for column in shared
                if self._is_numeric_series(reference_frame[column])
                and self._is_numeric_series(current_frame[column])
            ]
        else:
            selected = [
                column
                for column in features
                if column in reference_frame and column in current_frame
            ]

        metrics: list[DriftMetric] = []
        psi_scores: dict[str, float] = {}

        for feature in selected:
            ref_values = self._as_float_values(reference_frame[feature])
            cur_values = self._as_float_values(current_frame[feature])
            if not ref_values or not cur_values:
                continue

            psi_value = self.calculate_psi(ref_values, cur_values)
            level = self._level_for_psi(psi_value)
            metrics.append(
                DriftMetric(
                    feature_name=feature,
                    metric_type="PSI",
                    value=psi_value,
                    threshold=self._warning_threshold,
                    level=level,
                )
            )
            psi_scores[feature] = psi_value

            kl_value = self.calculate_kl_divergence(ref_values, cur_values)
            metrics.append(
                DriftMetric(
                    feature_name=feature,
                    metric_type="KL",
                    value=kl_value,
                    threshold=self._warning_threshold,
                    level=level if kl_value > 0.05 else "ok",
                )
            )

            ks_result = self.calculate_ks_test(ref_values, cur_values)
            ks_level = (
                "danger"
                if ks_result["p_value"] < 0.01
                else "warning"
                if ks_result["p_value"] < 0.05
                else "ok"
            )
            metrics.append(
                DriftMetric(
                    feature_name=feature,
                    metric_type="KS",
                    value=ks_result["statistic"],
                    threshold=0.01,
                    level=ks_level,
                )
            )

        overall = self._overall_status(metric.level for metric in metrics)
        top_features = [
            name
            for name, _score in sorted(
                psi_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
        ]
        recommended_action = (
            "rollback_or_retrain"
            if overall == "danger"
            else "monitor_and_investigate"
            if overall == "warning"
            else "no_action"
        )
        return DriftReport(
            metrics=metrics,
            overall_status=overall,
            top_drifting_features=top_features,
            recommended_action=recommended_action,
        )

    def _to_distribution(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        bins: int | None = None,
    ) -> tuple[list[float], list[float]]:
        ref = self._as_float_values(reference)
        cur = self._as_float_values(current)
        if self._is_distribution(ref) and self._is_distribution(cur) and len(ref) == len(cur):
            ref_dist = list(ref)
            cur_dist = list(cur)
        else:
            ref_dist, cur_dist = self._histogram_distribution(ref, cur, bins=bins or self._bins)

        ref_dist = self._normalize_distribution(ref_dist)
        cur_dist = self._normalize_distribution(cur_dist)
        return ref_dist, cur_dist

    def _normalize_distribution(self, values: Sequence[float]) -> list[float]:
        clipped = [max(float(value), self._smoothing) for value in values]
        total = sum(clipped)
        if total <= 0:
            return [1.0]
        return [value / total for value in clipped]

    @staticmethod
    def _ks_statistic(reference: Sequence[float], current: Sequence[float]) -> float:
        combined = sorted(set(reference) | set(current))
        if not combined:
            return 0.0

        max_delta = 0.0
        for value in combined:
            ref_cdf = bisect_right(reference, value) / len(reference)
            cur_cdf = bisect_right(current, value) / len(current)
            max_delta = max(max_delta, abs(ref_cdf - cur_cdf))
        return max_delta

    @staticmethod
    def _ks_p_value(statistic: float, reference_size: int, current_size: int) -> float:
        if statistic <= 0 or reference_size <= 0 or current_size <= 0:
            return 1.0
        n_eff = (reference_size * current_size) / (reference_size + current_size)
        if n_eff <= 0:
            return 1.0
        lambda_value = (math.sqrt(n_eff) + 0.12 + (0.11 / math.sqrt(n_eff))) * statistic
        series = 0.0
        for term_index in range(1, 101):
            term = (-1) ** (term_index - 1) * math.exp(-2.0 * (term_index**2) * (lambda_value**2))
            series += term
            if abs(term) < 1e-12:
                break
        return max(0.0, min(1.0, 2.0 * series))

    @staticmethod
    def _histogram_distribution(
        reference: Sequence[float],
        current: Sequence[float],
        *,
        bins: int,
    ) -> tuple[list[float], list[float]]:
        combined = [*reference, *current]
        if not combined:
            return [1.0], [1.0]
        lower = min(combined)
        upper = max(combined)
        if math.isclose(lower, upper):
            return [float(len(reference))], [float(len(current))]

        bucket_count = max(int(bins), 1)
        step = (upper - lower) / bucket_count
        edges = [lower + (step * index) for index in range(bucket_count)]
        ref_counts = [0.0] * bucket_count
        cur_counts = [0.0] * bucket_count
        for value in reference:
            ref_counts[DriftAnalyzer._histogram_index(value, edges)] += 1.0
        for value in current:
            cur_counts[DriftAnalyzer._histogram_index(value, edges)] += 1.0
        return ref_counts, cur_counts

    @staticmethod
    def _histogram_index(value: float, edges: Sequence[float]) -> int:
        index = bisect_right(edges, value) - 1
        return max(0, min(index, len(edges) - 1))

    @staticmethod
    def _is_distribution(values: Sequence[float]) -> bool:
        return (
            bool(values)
            and all(value >= 0 for value in values)
            and math.isclose(
                sum(values),
                1.0,
                abs_tol=1e-6,
            )
        )

    @staticmethod
    def _is_numeric_series(values: Sequence[object]) -> bool:
        numeric_values = DriftAnalyzer._as_float_values(values)
        return bool(numeric_values)

    @staticmethod
    def _as_float_values(values: Sequence[object]) -> list[float]:
        parsed: list[float] = []
        for value in values:
            if value is None or value == "":
                continue
            if isinstance(value, bool):
                parsed.append(float(value))
                continue
            if isinstance(value, (int, float)):
                number = float(value)
            else:
                try:
                    number = float(cast(Any, value))
                except (TypeError, ValueError):
                    continue
            if math.isnan(number):
                continue
            parsed.append(number)
        return parsed

    def _level_for_psi(self, psi_value: float) -> str:
        if psi_value > self._danger_threshold:
            return "danger"
        if psi_value > self._warning_threshold:
            return "warning"
        return "ok"

    @staticmethod
    def _overall_status(levels: Iterable[str]) -> str:
        severity = {"ok": 0, "warning": 1, "danger": 2}
        current = "ok"
        for level in levels:
            if severity.get(level, 0) > severity[current]:
                current = level
        return current

    @staticmethod
    def _coerce_frame(data: object) -> dict[str, list[object]]:
        if DriftAnalyzer._looks_like_pandas_frame(data):
            return DriftAnalyzer._frame_from_pandas(data)
        if isinstance(data, (str, Path)):
            return DriftAnalyzer._frame_from_path(Path(data))
        if isinstance(data, Mapping):
            return DriftAnalyzer._frame_from_mapping(data)
        return DriftAnalyzer._frame_from_records(data)

    @staticmethod
    def _looks_like_pandas_frame(data: object) -> bool:
        module_name = getattr(type(data), "__module__", "")
        has_frame_protocol = hasattr(data, "to_dict") and hasattr(data, "columns")
        return (
            module_name == _PANDAS_FRAME_MODULE
            or module_name.startswith(f"{_PANDAS_FRAME_MODULE}.")
        ) and has_frame_protocol

    @staticmethod
    def _frame_from_pandas(data: object) -> dict[str, list[object]]:
        frame_dict = cast(Any, data).to_dict(orient="list")
        return {str(column): list(values) for column, values in frame_dict.items()}

    @staticmethod
    def _frame_from_path(path: Path) -> dict[str, list[object]]:
        suffix = path.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            delimiter = "\t" if suffix == ".tsv" else ","
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter=delimiter)
                return DriftAnalyzer._frame_from_records(list(reader))
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return DriftAnalyzer._frame_from_mapping(payload)
            return DriftAnalyzer._frame_from_records(payload)
        if suffix in _SUPPORTED_PANDAS_SUFFIXES:
            pandas = DriftAnalyzer._load_optional_pandas()
            if suffix in {".parquet", ".pq"}:
                return DriftAnalyzer._frame_from_pandas(pandas.read_parquet(path))
            return DriftAnalyzer._frame_from_pandas(pandas.read_excel(path))
        raise ValueError(f"Unsupported drift snapshot format: {path.suffix}")

    @staticmethod
    def _frame_from_mapping(data: Mapping[str, object]) -> dict[str, list[object]]:
        frame: dict[str, list[object]] = {}
        for column, value in data.items():
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                frame[str(column)] = list(value)
            else:
                frame[str(column)] = [value]
        return frame

    @staticmethod
    def _frame_from_records(data: object) -> dict[str, list[object]]:
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes, bytearray)):
            raise ValueError("Drift data must be a mapping, records, DataFrame, or file path")
        records = list(data)
        if not records:
            return {}
        if all(isinstance(record, Mapping) for record in records):
            columns = {str(key) for record in records for key in record}
            return {
                column: [record.get(column) for record in records if isinstance(record, Mapping)]
                for column in sorted(columns)
            }
        return {"value": records}

    @staticmethod
    def _load_optional_pandas() -> Any:
        try:
            return import_module("pandas")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pandas is required for parquet/xlsx drift snapshots in this environment"
            ) from exc
