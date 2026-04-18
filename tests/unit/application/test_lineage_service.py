"""Tests for lineage capture service and hook integration."""

from __future__ import annotations

import hashlib
import json

import pytest

from ds_agent.agent.governance_hooks import LineageCaptureHook
from ds_agent.agent.hooks import HookContext
from ds_agent.application.services.lineage_capture_service import LineageCaptureService
from ds_agent.domain.entities.lineage import LineageRecordType
from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore


def _service(tmp_path) -> LineageCaptureService:
    return LineageCaptureService(SqliteLineageStore(str(tmp_path / "lineage.db")))


class TestLineageCaptureService:
    def test_capture_dataset_records_hash_and_schema(self, tmp_path):
        data_path = tmp_path / "train.csv"
        data_path.write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
        service = _service(tmp_path)

        record = service.capture_dataset(
            str(data_path),
            schema=["x", "y"],
            row_count=2,
            session_id="session-a",
        )

        expected_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
        assert record.record_type == LineageRecordType.DATASET
        assert record.content["sha256"] == expected_hash
        assert record.content["row_count"] == 2

    def test_trace_walks_dataset_feature_model_chain(self, tmp_path):
        service = _service(tmp_path)
        dataset = service.capture_dataset(
            "data/train.csv", schema=["a"], row_count=10, session_id="s1"
        )
        feature = service.capture_feature(
            "df['b']=1", {"input": "data/train.csv"}, dataset.id, session_id="s1"
        )
        model = service.capture_model(
            hyperparams={"max_depth": 4},
            seed=42,
            env_info={"python": "3.11"},
            feature_id=feature.id,
            session_id="s1",
            model_type="lightgbm",
        )
        trace = service.trace(model.id)
        assert [record.record_type for record in trace] == [
            LineageRecordType.DATASET,
            LineageRecordType.FEATURE,
            LineageRecordType.MODEL,
        ]

    def test_capture_decision_records_memo(self, tmp_path):
        service = _service(tmp_path)
        record = service.capture_decision(
            what="Select LightGBM",
            why="Baseline +5% with better latency",
            alternatives_considered=["RandomForest"],
            session_id="s2",
        )
        assert record.record_type == LineageRecordType.DECISION
        assert record.content["why"] == "Baseline +5% with better latency"


class TestLineageCaptureHook:
    @pytest.mark.asyncio
    async def test_records_lineage_for_data_loader_and_training(self, tmp_path):
        data_path = tmp_path / "train.csv"
        data_path.write_text("x,target\n1,0\n2,1\n", encoding="utf-8")
        service = _service(tmp_path)
        hook = LineageCaptureHook(service=service)
        events: list[tuple[str, dict]] = []
        context = HookContext(session_id="hook-session", emit=lambda e, p: events.append((e, p)))

        result = json.dumps({"shape": [2, 2], "columns": ["x", "target"]})
        await hook.post_tool_use(
            "data_loader", {"file_path": str(data_path)}, result, False, context
        )
        await hook.post_tool_use(
            "train_model",
            {
                "code": "model.fit(X_train, y_train)\nrandom_state=42",
                "model_type": "random_forest",
            },
            "accuracy: 0.82",
            False,
            context,
        )

        dataset = service.latest_for_session("hook-session", record_type=LineageRecordType.DATASET)
        model = service.latest_for_session("hook-session", record_type=LineageRecordType.MODEL)
        assert dataset is not None
        assert model is not None
        assert model.parent_id == dataset.id
        assert [event for event, _ in events] == ["lineage.recorded", "lineage.recorded"]
