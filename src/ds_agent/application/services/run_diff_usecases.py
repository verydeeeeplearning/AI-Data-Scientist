"""Decision OS run-diff use cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from ds_agent.application.ports.run_diff_support import (
    ExperimentRunReader,
    MetricDirectionLabel,
    MetricDirectionResolver,
)
from ds_agent.domain.entities.experiment import ExperimentRun
from ds_agent.domain.entities.feature import FeatureRef
from ds_agent.domain.entities.run_diff import (
    ConfigDiff,
    FeatureSetDiff,
    MetricDelta,
    RunDiff,
    VerifierDiff,
)


class RunDiffEngine:
    """Compute a deterministic Decision OS run diff from two experiment runs."""

    def __init__(
        self,
        experiment_runs: ExperimentRunReader,
        metric_directions: MetricDirectionResolver,
    ) -> None:
        self._experiment_runs = experiment_runs
        self._metric_directions = metric_directions

    def compare(self, run_a_id: str, run_b_id: str) -> RunDiff:
        run_a = self._load(run_a_id)
        run_b = self._load(run_b_id)

        feature_diff = self._feature_diff(run_a, run_b)
        config_diff = self._config_diff(run_a, run_b)
        metric_diff = self._metric_diff(run_a, run_b)
        verifier_diff = self._verifier_diff(run_a, run_b)
        summary = self._summary_markdown(
            run_a=run_a,
            run_b=run_b,
            feature_diff=feature_diff,
            config_diff=config_diff,
            metric_diff=metric_diff,
            verifier_diff=verifier_diff,
        )
        return RunDiff(
            run_a_id=run_a.run_id,
            run_b_id=run_b.run_id,
            feature_set=feature_diff,
            config=config_diff,
            metrics=metric_diff,
            verifier=verifier_diff,
            code_ref=(run_a.method.code_ref, run_b.method.code_ref),
            data_snapshot=(run_a.data_snapshot_uri, run_b.data_snapshot_uri),
            summary_markdown=summary,
        )

    def _load(self, run_id: str) -> ExperimentRun:
        run = self._experiment_runs.get_run(run_id)
        if run is None:
            raise LookupError(f"Experiment run not found: {run_id}")
        return run

    @staticmethod
    def _feature_diff(run_a: ExperimentRun, run_b: ExperimentRun) -> FeatureSetDiff:
        map_a = {ref.feature_id: ref.version for ref in run_a.feature_refs}
        map_b = {ref.feature_id: ref.version for ref in run_b.feature_refs}

        added = [
            FeatureRef(feature_id=feature_id, version=map_b[feature_id])
            for feature_id in sorted(set(map_b) - set(map_a))
        ]
        removed = [
            FeatureRef(feature_id=feature_id, version=map_a[feature_id])
            for feature_id in sorted(set(map_a) - set(map_b))
        ]
        version_changed = [
            (feature_id, map_a[feature_id], map_b[feature_id])
            for feature_id in sorted(set(map_a) & set(map_b))
            if map_a[feature_id] != map_b[feature_id]
        ]
        return FeatureSetDiff(
            added=added,
            removed=removed,
            version_changed=version_changed,
        )

    @staticmethod
    def _config_diff(run_a: ExperimentRun, run_b: ExperimentRun) -> ConfigDiff:
        config_a = run_a.to_diffable().config
        config_b = run_b.to_diffable().config
        changed: dict[str, tuple[object, object]] = {}
        added: dict[str, object] = {}
        removed: dict[str, object] = {}
        RunDiffEngine._diff_mapping(
            config_a,
            config_b,
            changed=changed,
            added=added,
            removed=removed,
        )
        return ConfigDiff(changed=changed, added=added, removed=removed)

    @staticmethod
    def _diff_mapping(
        left: Mapping[str, object],
        right: Mapping[str, object],
        *,
        changed: dict[str, tuple[object, object]],
        added: dict[str, object],
        removed: dict[str, object],
        prefix: str = "",
    ) -> None:
        left_keys = set(left)
        right_keys = set(right)
        for key in sorted(left_keys - right_keys):
            removed[f"{prefix}{key}"] = left[key]
        for key in sorted(right_keys - left_keys):
            added[f"{prefix}{key}"] = right[key]
        for key in sorted(left_keys & right_keys):
            left_value = left[key]
            right_value = right[key]
            dotted = f"{prefix}{key}"
            if isinstance(left_value, Mapping) and isinstance(right_value, Mapping):
                RunDiffEngine._diff_mapping(
                    left_value,
                    right_value,
                    changed=changed,
                    added=added,
                    removed=removed,
                    prefix=f"{dotted}.",
                )
                continue
            if left_value != right_value:
                changed[dotted] = (left_value, right_value)

    def _metric_diff(self, run_a: ExperimentRun, run_b: ExperimentRun) -> list[MetricDelta]:
        metrics_a = run_a.result.metrics
        metrics_b = run_b.result.metrics
        deltas: list[MetricDelta] = []
        for metric in sorted(set(metrics_a) & set(metrics_b)):
            from_value = float(metrics_a[metric])
            to_value = float(metrics_b[metric])
            delta = to_value - from_value
            deltas.append(
                MetricDelta(
                    metric=metric,
                    from_value=from_value,
                    to_value=to_value,
                    delta=delta,
                    direction=self._delta_direction(metric, delta),
                )
            )
        return deltas

    def _delta_direction(
        self, metric: str, delta: float
    ) -> Literal["better", "worse", "neutral"]:
        if delta == 0:
            return "neutral"
        direction = self._metric_directions.direction_for(metric)
        if direction == "neutral":
            return "neutral"
        if direction == "higher_is_better":
            return "better" if delta > 0 else "worse"
        return "better" if delta < 0 else "worse"

    @staticmethod
    def _verifier_diff(run_a: ExperimentRun, run_b: ExperimentRun) -> VerifierDiff:
        summary_a = run_a.verifier_summary or {}
        summary_b = run_b.verifier_summary or {}
        findings_a = set(run_a.verifier_findings)
        findings_b = set(run_b.verifier_findings)
        return VerifierDiff(
            statistical=(
                summary_a.get("statistical", "UNKNOWN"),
                summary_b.get("statistical", "UNKNOWN"),
            ),
            data=(summary_a.get("data", "UNKNOWN"), summary_b.get("data", "UNKNOWN")),
            policy=(summary_a.get("policy", "UNKNOWN"), summary_b.get("policy", "UNKNOWN")),
            new_findings=sorted(findings_b - findings_a),
            resolved_findings=sorted(findings_a - findings_b),
        )

    @staticmethod
    def _summary_markdown(
        *,
        run_a: ExperimentRun,
        run_b: ExperimentRun,
        feature_diff: FeatureSetDiff,
        config_diff: ConfigDiff,
        metric_diff: list[MetricDelta],
        verifier_diff: VerifierDiff,
    ) -> str:
        lines = [
            f"# Run Diff: {run_b.run_id} vs {run_a.run_id}",
            "",
            "## Feature Changes",
        ]
        if not (feature_diff.added or feature_diff.removed or feature_diff.version_changed):
            lines.append("- No feature-set changes.")
        else:
            lines.extend(f"- Added `{ref.feature_id}` v{ref.version}" for ref in feature_diff.added)
            lines.extend(
                f"- Removed `{ref.feature_id}` v{ref.version}" for ref in feature_diff.removed
            )
            lines.extend(
                f"- Updated `{feature_id}`: v{from_v} -> v{to_v}"
                for feature_id, from_v, to_v in feature_diff.version_changed
            )

        lines.extend(["", "## Config Changes"])
        if not (config_diff.changed or config_diff.added or config_diff.removed):
            lines.append("- No config changes.")
        else:
            lines.extend(
                f"- Changed `{key}`: `{before}` -> `{after}`"
                for key, (before, after) in config_diff.changed.items()
            )
            lines.extend(f"- Added `{key}`: `{value}`" for key, value in config_diff.added.items())
            lines.extend(
                f"- Removed `{key}`: `{value}`" for key, value in config_diff.removed.items()
            )

        lines.extend(["", "## Metric Delta"])
        if not metric_diff:
            lines.append("- No overlapping metrics to compare.")
        else:
            lines.extend(
                f"- `{delta.metric}`: {delta.from_value} -> {delta.to_value} "
                f"({delta.delta:+.4f}, {delta.direction})"
                for delta in metric_diff
            )

        lines.extend(
            [
                "",
                "## Verifier",
                f"- Statistical: {verifier_diff.statistical[0]} -> {verifier_diff.statistical[1]}",
                f"- Data: {verifier_diff.data[0]} -> {verifier_diff.data[1]}",
                f"- Policy: {verifier_diff.policy[0]} -> {verifier_diff.policy[1]}",
            ]
        )
        if verifier_diff.new_findings:
            lines.extend(f"- New finding: {finding}" for finding in verifier_diff.new_findings)
        if verifier_diff.resolved_findings:
            lines.extend(
                f"- Resolved finding: {finding}" for finding in verifier_diff.resolved_findings
            )

        lines.extend(
            [
                "",
                "## Reproducibility",
                f"- Data snapshot: `{run_a.data_snapshot_uri}` -> `{run_b.data_snapshot_uri}`",
                f"- Code ref: `{run_a.method.code_ref}` -> `{run_b.method.code_ref}`",
            ]
        )
        return "\n".join(lines).strip() + "\n"


class CompareRunsUseCase:
    """Application-facing wrapper for run-diff execution."""

    def __init__(self, engine: RunDiffEngine) -> None:
        self._engine = engine

    def execute(self, run_a_id: str, run_b_id: str) -> RunDiff:
        return self._engine.compare(run_a_id, run_b_id)


class HeuristicMetricDirectionResolver:
    """Default metric-direction resolver used when no catalog entry is available."""

    _LOWER_IS_BETTER_HINTS = (
        "loss",
        "error",
        "rmse",
        "mae",
        "mse",
        "latency",
        "fp",
        "false_positive",
        "drift",
    )

    def direction_for(self, metric_name: str) -> MetricDirectionLabel:
        normalized = metric_name.strip().casefold()
        if not normalized:
            return "neutral"
        if any(hint in normalized for hint in self._LOWER_IS_BETTER_HINTS):
            return "lower_is_better"
        return "higher_is_better"
