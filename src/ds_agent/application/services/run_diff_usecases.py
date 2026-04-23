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
    ArtifactDiffEntry,
    ConfigDiff,
    DecisionTraceDiffEntry,
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
        artifact_diff = self._artifact_diff(run_a, run_b)
        verifier_diff = self._verifier_diff(run_a, run_b)
        decision_diff = self._decision_diff(
            run_a=run_a,
            run_b=run_b,
            feature_diff=feature_diff,
            config_diff=config_diff,
            verifier_diff=verifier_diff,
        )
        summary = self._summary_markdown(
            run_a=run_a,
            run_b=run_b,
            feature_diff=feature_diff,
            config_diff=config_diff,
            metric_diff=metric_diff,
            artifact_diff=artifact_diff,
            decision_diff=decision_diff,
            verifier_diff=verifier_diff,
        )
        return RunDiff(
            run_a_id=run_a.run_id,
            run_b_id=run_b.run_id,
            feature_set=feature_diff,
            config=config_diff,
            metrics=metric_diff,
            artifacts=artifact_diff,
            decisions=decision_diff,
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
            highlighted, significance_note = self._metric_highlight(metric, from_value, to_value)
            deltas.append(
                MetricDelta(
                    metric=metric,
                    from_value=from_value,
                    to_value=to_value,
                    delta=delta,
                    direction=self._delta_direction(metric, delta),
                    highlighted=highlighted,
                    significance_note=significance_note,
                )
            )
        return deltas

    @staticmethod
    def _metric_highlight(
        metric: str,
        from_value: float,
        to_value: float,
    ) -> tuple[bool, str | None]:
        delta = to_value - from_value
        baseline = abs(from_value)
        if baseline < 1e-9:
            if abs(delta) >= 0.05:
                return (
                    True,
                    (
                        f"Heuristic highlight for {metric}: absolute delta "
                        f"{delta:+.4f} on a near-zero baseline."
                    ),
                )
            return False, None

        relative_change = abs(delta) / baseline
        if relative_change >= 0.05:
            return (
                True,
                (
                    f"Heuristic highlight for {metric}: relative change "
                    f"{relative_change * 100:.1f}% exceeds the 5.0% compare threshold."
                ),
            )
        return False, None

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
    def _artifact_diff(
        run_a: ExperimentRun,
        run_b: ExperimentRun,
    ) -> list[ArtifactDiffEntry]:
        entries: list[ArtifactDiffEntry] = []

        plots_a = set(run_a.result.plots)
        plots_b = set(run_b.result.plots)
        for plot in sorted(plots_a - plots_b):
            entries.append(
                ArtifactDiffEntry(
                    key=f"plot:{plot}",
                    label=RunDiffEngine._artifact_label(plot),
                    artifact_kind="plot",
                    status="removed",
                    run_a_value=plot,
                    summary="Plot only exists on the base run.",
                )
            )
        for plot in sorted(plots_b - plots_a):
            entries.append(
                ArtifactDiffEntry(
                    key=f"plot:{plot}",
                    label=RunDiffEngine._artifact_label(plot),
                    artifact_kind="plot",
                    status="added",
                    run_b_value=plot,
                    summary="Plot only exists on the candidate run.",
                )
            )

        review_a = {artifact.skill_name: artifact for artifact in run_a.review_artifacts}
        review_b = {artifact.skill_name: artifact for artifact in run_b.review_artifacts}
        for skill_name in sorted(set(review_a) | set(review_b)):
            artifact_a = review_a.get(skill_name)
            artifact_b = review_b.get(skill_name)
            if artifact_a is not None and artifact_b is not None:
                if (
                    artifact_a.summary == artifact_b.summary
                    and (artifact_a.narrative or "") == (artifact_b.narrative or "")
                ):
                    continue
                entries.append(
                    ArtifactDiffEntry(
                        key=f"review:{skill_name}",
                        label=RunDiffEngine._humanize_slug(skill_name),
                        artifact_kind="review_artifact",
                        status="changed",
                        run_a_value=artifact_a.summary,
                        run_b_value=artifact_b.summary,
                        summary="Review artifact recommendation changed between runs.",
                    )
                )
                continue
            if artifact_a is not None:
                entries.append(
                    ArtifactDiffEntry(
                        key=f"review:{skill_name}",
                        label=RunDiffEngine._humanize_slug(skill_name),
                        artifact_kind="review_artifact",
                        status="removed",
                        run_a_value=artifact_a.summary,
                        summary="Review artifact only exists on the base run.",
                    )
                )
                continue
            if artifact_b is not None:
                entries.append(
                    ArtifactDiffEntry(
                        key=f"review:{skill_name}",
                        label=RunDiffEngine._humanize_slug(skill_name),
                        artifact_kind="review_artifact",
                        status="added",
                        run_b_value=artifact_b.summary,
                        summary="Review artifact only exists on the candidate run.",
                    )
                )

        return entries

    @staticmethod
    def _decision_diff(
        *,
        run_a: ExperimentRun,
        run_b: ExperimentRun,
        feature_diff: FeatureSetDiff,
        config_diff: ConfigDiff,
        verifier_diff: VerifierDiff,
    ) -> list[DecisionTraceDiffEntry]:
        entries: list[DecisionTraceDiffEntry] = []

        if run_a.hypothesis != run_b.hypothesis:
            entries.append(
                DecisionTraceDiffEntry(
                    key="hypothesis",
                    decision_kind="hypothesis",
                    divergence_point="Hypothesis framing changed.",
                    run_a_summary=RunDiffEngine._format_hypothesis(run_a),
                    run_b_summary=RunDiffEngine._format_hypothesis(run_b),
                )
            )

        if feature_diff.added or feature_diff.removed or feature_diff.version_changed:
            entries.append(
                DecisionTraceDiffEntry(
                    key="feature-strategy",
                    decision_kind="feature_strategy",
                    divergence_point="Feature strategy changed.",
                    run_a_summary=RunDiffEngine._format_feature_strategy(run_a),
                    run_b_summary=RunDiffEngine._format_feature_strategy(run_b),
                )
            )

        if (
            run_a.method.model_family != run_b.method.model_family
            or config_diff.changed
            or config_diff.added
            or config_diff.removed
        ):
            entries.append(
                DecisionTraceDiffEntry(
                    key="model-strategy",
                    decision_kind="model_strategy",
                    divergence_point="Model strategy changed.",
                    run_a_summary=RunDiffEngine._format_model_strategy(run_a, config_diff),
                    run_b_summary=RunDiffEngine._format_model_strategy(run_b, config_diff),
                )
            )

        if (
            verifier_diff.statistical[0] != verifier_diff.statistical[1]
            or verifier_diff.data[0] != verifier_diff.data[1]
            or verifier_diff.policy[0] != verifier_diff.policy[1]
            or verifier_diff.new_findings
            or verifier_diff.resolved_findings
        ):
            entries.append(
                DecisionTraceDiffEntry(
                    key="verifier",
                    decision_kind="verifier",
                    divergence_point="Verifier posture changed.",
                    run_a_summary=RunDiffEngine._format_verifier_summary(run_a),
                    run_b_summary=RunDiffEngine._format_verifier_summary(run_b),
                )
            )

        review_a = {artifact.skill_name: artifact for artifact in run_a.review_artifacts}
        review_b = {artifact.skill_name: artifact for artifact in run_b.review_artifacts}
        for skill_name in sorted(set(review_a) | set(review_b)):
            artifact_a = review_a.get(skill_name)
            artifact_b = review_b.get(skill_name)
            if (
                artifact_a is not None
                and artifact_b is not None
                and artifact_a.summary == artifact_b.summary
                and (artifact_a.narrative or "") == (artifact_b.narrative or "")
            ):
                continue
            entries.append(
                DecisionTraceDiffEntry(
                    key=f"review-artifact:{skill_name}",
                    decision_kind="review_artifact",
                    divergence_point=(
                        f"{RunDiffEngine._humanize_slug(skill_name)} recommendation changed."
                    ),
                    run_a_summary=RunDiffEngine._format_review_artifact_summary(artifact_a),
                    run_b_summary=RunDiffEngine._format_review_artifact_summary(artifact_b),
                )
            )

        return entries

    @staticmethod
    def _artifact_label(value: str) -> str:
        if "/" in value:
            return value.rsplit("/", maxsplit=1)[-1]
        if "\\" in value:
            return value.rsplit("\\", maxsplit=1)[-1]
        return value

    @staticmethod
    def _humanize_slug(value: str) -> str:
        return value.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _format_hypothesis(run: ExperimentRun) -> str:
        return (
            f"{run.hypothesis.statement} "
            f"(expected: {run.hypothesis.expected_effect}; rationale: {run.hypothesis.rationale})"
        )

    @staticmethod
    def _format_feature_strategy(run: ExperimentRun) -> str:
        if not run.feature_refs:
            return "No tracked features."
        feature_refs = sorted(run.feature_refs, key=lambda ref: ref.feature_id)
        return ", ".join(
            f"{ref.feature_id} v{ref.version}" for ref in feature_refs
        )

    @staticmethod
    def _format_model_strategy(run: ExperimentRun, config_diff: ConfigDiff) -> str:
        changed_keys = [
            *sorted(config_diff.changed),
            *sorted(config_diff.added),
            *sorted(config_diff.removed),
        ]
        changed_preview = ", ".join(changed_keys[:3])
        if len(changed_keys) > 3:
            changed_preview += ", ..."
        seed = "n/a" if run.method.random_seed is None else str(run.method.random_seed)
        if changed_preview:
            return f"{run.method.model_family}; seed={seed}; touched: {changed_preview}"
        return f"{run.method.model_family}; seed={seed}"

    @staticmethod
    def _format_verifier_summary(run: ExperimentRun) -> str:
        summary = run.verifier_summary or {}
        statistical = summary.get("statistical", "UNKNOWN")
        data = summary.get("data", "UNKNOWN")
        policy = summary.get("policy", "UNKNOWN")
        findings = ", ".join(run.verifier_findings) if run.verifier_findings else "none"
        return (
            f"statistical={statistical}; data={data}; policy={policy}; "
            f"findings={findings}"
        )

    @staticmethod
    def _format_review_artifact_summary(artifact: object) -> str | None:
        if artifact is None:
            return "Not present."
        summary = getattr(artifact, "summary", None)
        narrative = getattr(artifact, "narrative", None)
        if isinstance(summary, str) and isinstance(narrative, str) and narrative.strip():
            return f"{summary} ({narrative})"
        if isinstance(summary, str):
            return summary
        return "Present."

    @staticmethod
    def _summary_markdown(
        *,
        run_a: ExperimentRun,
        run_b: ExperimentRun,
        feature_diff: FeatureSetDiff,
        config_diff: ConfigDiff,
        metric_diff: list[MetricDelta],
        artifact_diff: list[ArtifactDiffEntry],
        decision_diff: list[DecisionTraceDiffEntry],
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
                + (f" — {delta.significance_note}" if delta.significance_note else "")
                for delta in metric_diff
            )

        lines.extend(["", "## Artifact Diff"])
        if not artifact_diff:
            lines.append("- No artifact-level changes.")
        else:
            lines.extend(
                (
                    f"- {entry.label} [{entry.artifact_kind}, {entry.status}]: "
                    f"{entry.summary}"
                )
                for entry in artifact_diff
            )

        lines.extend(["", "## Decision Trace"])
        if not decision_diff:
            lines.append("- No decision-trace divergences detected.")
        else:
            lines.extend(
                (
                    f"- {entry.divergence_point} "
                    f"({entry.run_a_summary or 'Not present.'} -> "
                    f"{entry.run_b_summary or 'Not present.'})"
                )
                for entry in decision_diff
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
