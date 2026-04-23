from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.result_card import (
    ExperimentMetric,
    KeyMetric,
    OtherCard,
    ResultCardSource,
    build_other_card,
    coerce_result_card,
)

NOW = datetime(2026, 4, 19, 9, 30, tzinfo=UTC)


def _source() -> ResultCardSource:
    return ResultCardSource(messageId="msg-1", runId="run-1", toolCallId="tool-1")


def test_coerce_insight_card_from_camel_case_payload() -> None:
    card = coerce_result_card(
        "insight",
        {
            "title": "Retention lifted",
            "keyMetric": {"label": "7d", "value": "+8.2%"},
            "evidence": ["cohort analysis", "feature importance"],
            "trustStatus": "partial",
            "quickActions": ["export_report", "compare_run"],
        },
        card_id="RC-1",
        result_id="result-1",
        created_at=NOW,
        source=_source(),
    )

    assert card.type == "insight"
    assert card.card_id == "RC-1"
    assert card.result_id == "result-1"
    assert card.title == "Retention lifted"
    assert card.key_metric == KeyMetric(label="7d", value="+8.2%")
    assert card.source.tool_call_id == "tool-1"


def test_coerce_experiment_card_from_plan_schema_payload() -> None:
    card = coerce_result_card(
        "experiment",
        {
            "runId": "run-77",
            "modelLabel": "XGBoost (d=6, n=500)",
            "dataVersion": "dataset-v3",
            "primaryMetric": {
                "name": "roc_auc",
                "value": 0.912,
                "deltaVsBaseline": 0.024,
            },
            "artifactRefs": [
                {
                    "artifactId": "artifact-1",
                    "ref": "artifact://chart-1",
                    "kind": "chart",
                }
            ],
        },
        card_id="RC-EXP-1",
        result_id="result-exp-1",
        created_at=NOW,
        source=_source(),
    )

    assert card.type == "experiment"
    assert card.card_id == "RC-EXP-1"
    assert card.result_id == "result-exp-1"
    assert card.primary_metric == ExperimentMetric(
        name="roc_auc",
        value=0.912,
        deltaVsBaseline=0.024,
    )
    assert card.artifact_refs[0].artifact_id == "artifact-1"


def test_coerce_risk_card_from_plan_schema_payload() -> None:
    card = coerce_result_card(
        "risk",
        {
            "severity": "high",
            "category": "overfit",
            "title": "Validation drift suspected",
            "target": "feature `purchase_30d`",
            "recommendation": "Rebuild leakage-safe feature set",
            "impact": "Offline score likely overstates production quality",
        },
        card_id="RC-RISK-1",
        result_id="result-risk-1",
        created_at=NOW,
        source=_source(),
    )

    assert card.type == "risk"
    assert card.severity == "high"
    assert card.category == "overfit"


def test_coerce_artifact_card_from_plan_schema_payload() -> None:
    card = coerce_result_card(
        "artifact",
        {
            "artifactKind": "report",
            "title": "Executive summary",
            "thumbnailUrl": "artifact://thumb-1",
            "fileRef": "artifact://report-1",
            "generatedByTool": "reporting",
            "sourceExperimentRunId": "run-88",
        },
        card_id="RC-ART-1",
        result_id="result-art-1",
        created_at=NOW,
        source=_source(),
    )

    assert card.type == "artifact"
    assert card.artifact_kind == "report"
    assert card.file_ref == "artifact://report-1"


def test_unknown_type_falls_back_to_other_card() -> None:
    card = coerce_result_card(
        "unsupported",
        {"title": "Maybe later", "body": "raw content"},
        card_id="RC-2",
        result_id="result-2",
        created_at=NOW,
        source=_source(),
    )

    assert isinstance(card, OtherCard)
    assert card.title == "Maybe later"
    assert card.body == '{"body": "raw content", "title": "Maybe later"}'


def test_invalid_payload_falls_back_to_other_card() -> None:
    card = coerce_result_card(
        "artifact",
        {
            "title": "Broken payload",
            "artifactKind": "chart",
            "fileRef": "artifact://chart-1",
        },
        card_id="RC-3",
        result_id="result-3",
        created_at=NOW,
        source=_source(),
    )

    assert isinstance(card, OtherCard)
    assert card.title == "Broken payload"
    assert "artifactKind" in card.body


def test_typed_model_rejects_invalid_metric_structure() -> None:
    card = coerce_result_card(
        "insight",
        {
            "title": "Broken insight",
            "keyMetric": {"value": "+1.0%"},
            "evidence": [],
            "trustStatus": "pending",
            "quickActions": [],
        },
        card_id="RC-4",
        result_id="result-4",
        created_at=NOW,
        source=_source(),
    )

    assert isinstance(card, OtherCard)
    assert "keyMetric" in card.body


def test_build_other_card_uses_explicit_body() -> None:
    card = build_other_card(
        card_id="RC-5",
        result_id="result-5",
        created_at=NOW,
        source=_source(),
        body="plain text",
        title="Fallback",
    )

    assert isinstance(card, OtherCard)
    assert card.title == "Fallback"
    assert card.body == "plain text"


def test_result_card_json_serializes_created_at_as_epoch_number() -> None:
    card = coerce_result_card(
        "insight",
        {
            "title": "Retention lifted",
            "evidence": ["cohort analysis"],
            "trustStatus": "verified",
            "quickActions": ["rerun"],
        },
        card_id="RC-JSON-1",
        result_id="result-json-1",
        created_at=NOW,
        source=_source(),
    )

    payload = card.model_dump(mode="json", by_alias=True)

    assert payload["cardId"] == "RC-JSON-1"
    assert payload["resultId"] == "result-json-1"
    assert isinstance(payload["createdAt"], float)


def test_legacy_id_payload_backfills_card_id_and_result_id() -> None:
    card = coerce_result_card(
        "insight",
        {
            "title": "Legacy payload",
            "evidence": ["history"],
            "trustStatus": "pending",
            "quickActions": [],
        },
        card_id="RC-LEGACY-1",
        result_id="result-legacy-1",
        created_at=NOW,
        source=_source(),
    )

    legacy_payload = card.model_dump(mode="python", by_alias=True)
    legacy_payload["id"] = legacy_payload.pop("cardId")
    legacy_payload.pop("resultId")

    restored = type(card).model_validate(legacy_payload)

    assert restored.card_id == "RC-LEGACY-1"
    assert restored.result_id == "RC-LEGACY-1"
