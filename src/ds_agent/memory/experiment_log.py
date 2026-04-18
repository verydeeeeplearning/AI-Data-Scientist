"""Experiment log JSONL append-only storage for ML experiments."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

from ds_agent.domain.entities.experiment import DiffableRun, ExperimentRun
from ds_agent.domain.entities.feature import FeatureRef
from ds_agent.domain.entities.review_artifact import ReviewArtifact

logger = structlog.get_logger()


class ExperimentLog:
    """Append-only JSONL experiment record storage."""

    def __init__(self, data_dir: str = "data/memory/experiment_log") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "experiments.jsonl"
        self._lock = threading.Lock()

    def log_experiment(
        self,
        project_id: str,
        model_type: str,
        task_type: str,
        metrics: dict,
        hyperparameters: dict | None = None,
        features: list[str] | None = None,
        data_shape: list[int] | None = None,
        notes: str | None = None,
        parent_experiment_id: str | None = None,
        dataset_hash: str | None = None,
        feature_recipe_hash: str | None = None,
        decision_memo: str | None = None,
        deployment_link: str | None = None,
        evaluation_set: str | None = None,
        code: str | None = None,
        feature_code: str | None = None,
        evaluation_code: str | None = None,
        data_paths: list[str] | None = None,
        seed: int | None = None,
        environment: dict | None = None,
    ) -> str:
        """Append a legacy experiment record. Returns experiment ID."""
        exp_id = str(uuid.uuid4())[:8]
        record: dict[str, object] = {
            "id": exp_id,
            "project_id": project_id,
            "model_type": model_type,
            "task_type": task_type,
            "metrics": metrics,
            "hyperparameters": hyperparameters or {},
            "features": features or [],
            "data_shape": data_shape,
            "notes": notes,
            "parent_experiment_id": parent_experiment_id,
            "dataset_hash": dataset_hash,
            "feature_recipe_hash": feature_recipe_hash,
            "decision_memo": decision_memo,
            "deployment_link": deployment_link,
            "evaluation_set": evaluation_set,
            "code": code,
            "feature_code": feature_code,
            "evaluation_code": evaluation_code,
            "data_paths": data_paths or [],
            "seed": seed,
            "environment": environment or {},
            "timestamp": time.time(),
        }
        self._append_record(record)
        return exp_id

    def record_extended(self, run: ExperimentRun) -> str:
        """Append a typed Decision OS experiment run and preserve legacy fields."""
        if self.get_experiment(run.run_id) is not None:
            raise ValueError(f"Experiment already exists: {run.run_id}")
        self._append_record(self._run_to_record(run))
        return run.run_id

    def upsert_review_artifact(self, run_id: str, artifact: ReviewArtifact) -> ExperimentRun:
        """Add or replace one review artifact for a stored typed run."""

        with self._lock:
            records = self._read_all_records_unlocked()
            for index in range(len(records) - 1, -1, -1):
                record = records[index]
                if record.get("id") != run_id:
                    continue
                run = self._record_to_run(record)
                artifacts = [
                    existing
                    for existing in run.review_artifacts
                    if existing.skill_name != artifact.skill_name
                ]
                artifacts.append(artifact)
                artifacts.sort(key=lambda item: (item.created_at, item.skill_name))
                updated_run = run.model_copy(update={"review_artifacts": artifacts})
                records[index] = self._run_to_record(updated_run)
                self._write_all_records_unlocked(records)
                return updated_run
        raise LookupError(f"Experiment run not found: {run_id}")

    def get_review_artifacts(self, run_id: str) -> list[ReviewArtifact]:
        """Return persisted review artifacts for one experiment run."""

        run = self.get_run(run_id)
        if run is None:
            raise LookupError(f"Experiment run not found: {run_id}")
        return run.review_artifacts

    def get_experiments(
        self,
        project_id: str | None = None,
        task_type: str | None = None,
        model_type: str | None = None,
        experiment_group: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query experiments with optional filters."""
        if not self._file.exists():
            return []

        results = []
        with self._lock, open(self._file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("experiment_log_line_parse_failed", error=str(e))
                    continue
                if project_id and record.get("project_id") != project_id:
                    continue
                if task_type and record.get("task_type") != task_type:
                    continue
                if model_type and record.get("model_type") != model_type:
                    continue
                if experiment_group and record.get("experiment_group") != experiment_group:
                    continue
                results.append(record)

        return results[-limit:]

    def get_experiment(self, experiment_id: str) -> dict | None:
        """Return one experiment record by id."""
        for record in self.get_experiments(limit=10_000):
            if record.get("id") == experiment_id:
                return record
        return None

    def get_run(self, run_id: str) -> ExperimentRun | None:
        """Return a typed experiment run, normalizing legacy JSONL records when needed."""
        record = self.get_experiment(run_id)
        if record is None:
            return None
        return self._record_to_run(record)

    def list_runs(
        self,
        experiment_group: str | None = None,
        *,
        owner: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ExperimentRun]:
        """List typed runs with optional Decision OS filters."""
        records = self.get_experiments(experiment_group=experiment_group, limit=10_000)
        runs = [self._record_to_run(record) for record in records]
        if owner is not None:
            runs = [run for run in runs if run.owner == owner]
        if status is not None:
            runs = [run for run in runs if run.status == status]
        return runs[-limit:]

    def to_diffable(self, run_id: str) -> DiffableRun | None:
        """Return the comparison-friendly projection for a stored run."""
        run = self.get_run(run_id)
        if run is None:
            return None
        return run.to_diffable()

    def get_children(self, experiment_id: str) -> list[dict]:
        """Return direct child experiments for a parent experiment id."""
        children: list[dict] = []
        for record in self.get_experiments(limit=10_000):
            if record.get("parent_experiment_id") == experiment_id:
                children.append(record)
        return children

    def get_best_experiment(
        self,
        project_id: str,
        metric_name: str,
        higher_is_better: bool = True,
    ) -> dict | None:
        """Get best experiment by a specific metric."""
        experiments = self.get_experiments(project_id=project_id)
        if not experiments:
            return None

        default = float("-inf") if higher_is_better else float("inf")

        def metric_value(exp: dict) -> float:
            return float(exp.get("metrics", {}).get(metric_name, default))

        fn = max if higher_is_better else min
        return fn(experiments, key=metric_value)

    def _append_record(self, record: dict[str, object]) -> None:
        with self._lock, open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def _run_to_record(self, run: ExperimentRun) -> dict[str, object]:
        return {
            "id": run.run_id,
            "project_id": run.experiment_group,
            "model_type": run.method.model_family,
            "task_type": "decision_os_experiment",
            "metrics": run.result.metrics,
            "hyperparameters": run.method.hyperparameters,
            "features": [ref.feature_id for ref in run.feature_refs],
            "notes": run.hypothesis.rationale,
            "parent_experiment_id": run.parent_run_id,
            "dataset_hash": run.data_snapshot_uri,
            "feature_recipe_hash": self._feature_recipe_signature(run.feature_refs),
            "decision_memo": run.hypothesis.statement,
            "deployment_link": None,
            "evaluation_set": self._window_signature(run.method.eval_window),
            "code": None,
            "feature_code": None,
            "evaluation_code": None,
            "data_paths": [],
            "seed": run.method.random_seed,
            "environment": {},
            "experiment_group": run.experiment_group,
            "sequence": run.sequence,
            "hypothesis": run.hypothesis.model_dump(mode="json"),
            "method": run.method.model_dump(mode="json"),
            "feature_refs": [ref.model_dump(mode="json") for ref in run.feature_refs],
            "data_snapshot_uri": run.data_snapshot_uri,
            "result": run.result.model_dump(mode="json"),
            "verifier_report_id": run.verifier_report_id,
            "verifier_summary": run.verifier_summary,
            "verifier_findings": run.verifier_findings,
            "created_at": run.created_at.isoformat(),
            "owner": run.owner,
            "status": run.status,
            "parent_run_id": run.parent_run_id,
            "promotion_state": run.promotion_state,
            "reproducibility_status": run.reproducibility_status,
            "review_artifacts_json": [
                item.model_dump(mode="json") for item in run.review_artifacts
            ],
            "extended_run": run.model_dump(mode="json"),
            "timestamp": run.created_at.timestamp(),
        }

    @staticmethod
    def _feature_recipe_signature(feature_refs: list[FeatureRef]) -> str:
        return json.dumps(
            {ref.feature_id: ref.version for ref in feature_refs},
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _window_signature(window: tuple[datetime, datetime] | None) -> str | None:
        if window is None:
            return None
        return f"{window[0].isoformat()}::{window[1].isoformat()}"

    def _read_all_records_unlocked(self) -> list[dict[str, object]]:
        if not self._file.exists():
            return []

        records: list[dict[str, object]] = []
        with open(self._file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("experiment_log_line_parse_failed", error=str(e))
        return records

    def _write_all_records_unlocked(self, records: list[dict[str, object]]) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, default=str) + "\n")

    @staticmethod
    def _record_to_run(record: dict) -> ExperimentRun:
        extended = record.get("extended_run")
        if isinstance(extended, dict):
            return ExperimentRun.model_validate(extended)

        feature_refs = ExperimentLog._normalize_feature_refs(record)
        metrics = record.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}

        expected_effect = "not recorded"
        if metrics:
            metric_name = next(iter(metrics))
            expected_effect = f"{metric_name} tracked"

        return ExperimentRun.model_validate(
            {
                "run_id": str(record.get("id") or record.get("run_id") or "unknown"),
                "experiment_group": str(
                    record.get("experiment_group") or record.get("project_id") or "legacy"
                ),
                "sequence": int(record.get("sequence") or 0),
                "hypothesis": record.get("hypothesis")
                or {
                    "statement": "Legacy experiment imported from JSONL log.",
                    "rationale": str(record.get("notes") or "Legacy experiment record."),
                    "expected_effect": expected_effect,
                },
                "method": record.get("method")
                or {
                    "model_family": str(record.get("model_type") or "unknown"),
                    "hyperparameters": record.get("hyperparameters") or {},
                    "random_seed": record.get("seed"),
                    "code_ref": str(
                        record.get("code_ref")
                        or record.get("feature_recipe_hash")
                        or "legacy:unknown"
                    ),
                    "nondeterminism_notes": None,
                },
                "feature_refs": feature_refs,
                "data_snapshot_uri": str(
                    record.get("data_snapshot_uri")
                    or record.get("dataset_hash")
                    or f"legacy://dataset/{record.get('id', 'unknown')}"
                ),
                "result": record.get("result") or {"metrics": metrics, "plots": []},
                "verifier_report_id": record.get("verifier_report_id"),
                "verifier_summary": record.get("verifier_summary"),
                "verifier_findings": record.get("verifier_findings") or [],
                "created_at": ExperimentLog._coerce_created_at(
                    record.get("created_at"),
                    record.get("timestamp"),
                ),
                "owner": str(record.get("owner") or "unknown"),
                "status": str(record.get("status") or "succeeded"),
                "parent_run_id": record.get("parent_run_id") or record.get("parent_experiment_id"),
                "promotion_state": str(record.get("promotion_state") or "none"),
                "reproducibility_status": str(record.get("reproducibility_status") or "unknown"),
                "review_artifacts": record.get("review_artifacts")
                or record.get("review_artifacts_json")
                or [],
            }
        )

    @staticmethod
    def _normalize_feature_refs(record: dict) -> list[dict[str, object]]:
        feature_refs_payload = record.get("feature_refs")
        if isinstance(feature_refs_payload, list) and feature_refs_payload:
            return [dict(item) for item in feature_refs_payload if isinstance(item, dict)]

        raw_features = record.get("features", [])
        if not isinstance(raw_features, list):
            return []
        return [
            {"feature_id": str(feature_id), "version": 1}
            for feature_id in raw_features
            if str(feature_id).strip()
        ]

    @staticmethod
    def _coerce_created_at(created_at: object, timestamp_value: object) -> datetime:
        if isinstance(created_at, str) and created_at.strip():
            return datetime.fromisoformat(created_at)
        if isinstance(timestamp_value, (int, float)):
            return datetime.fromtimestamp(float(timestamp_value), UTC)
        return datetime.now(UTC)
