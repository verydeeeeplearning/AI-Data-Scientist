from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.application.usecases.preview_uploaded_file_usecase import PreviewUploadedFileUseCase


@pytest.fixture
def usecase(tmp_path) -> PreviewUploadedFileUseCase:
    return PreviewUploadedFileUseCase(str(tmp_path))


def test_preview_uploaded_file_csv_builds_schema_quality_and_target(
    tmp_path,
    usecase: PreviewUploadedFileUseCase,
) -> None:
    path = Path(tmp_path) / "customers.csv"
    path.write_text(
        "\n".join(
            [
                "customer_id,churn,monthly_spend,segment",
                "1,0,10,starter",
                "2,1,12,starter",
                "3,0,11,growth",
                "4,1,13,starter",
                "5,0,14,enterprise",
                "5,0,14,enterprise",
                "6,,2000,enterprise",
            ]
        ),
        encoding="utf-8",
    )

    result = usecase.execute("customers.csv", head_rows=1000, sample_rows=5)

    assert result.format == "csv"
    assert result.file_id == "customers.csv"
    assert result.workspace_path == "customers.csv"
    assert result.row_count_estimate == 7
    assert len(result.sample_rows) == 5
    assert result.sample_rows[0]["customer_id"] == 1
    assert result.columns[0].name == "customer_id"
    assert result.columns[0].dtype == "int"
    assert result.columns[1].name == "churn"
    assert result.columns[1].dtype == "int"
    assert result.columns[1].null_count == 1
    assert pytest.approx(result.data_quality.duplicate_row_ratio, rel=0, abs=1e-6) == (1 / 7)
    assert "monthly_spend" in result.data_quality.outlier_columns
    assert result.suggested_target is not None
    assert result.suggested_target.column_name == "churn"
    assert result.suggested_target.confidence == "high"
    assert [action.id for action in result.suggested_actions] == [
        "run_eda",
        "baseline_after_target",
        "validate_schema",
    ]
    assert result.suggested_actions[1].requires_target is True


def test_preview_uploaded_file_json_supports_record_arrays(
    tmp_path,
    usecase: PreviewUploadedFileUseCase,
) -> None:
    path = Path(tmp_path) / "records.json"
    path.write_text(
        """
        [
          {"label": 1, "score": 0.91, "city": "Seoul"},
          {"label": 0, "score": 0.12, "city": "Busan"}
        ]
        """.strip(),
        encoding="utf-8",
    )

    result = usecase.execute("records.json", head_rows=1000, sample_rows=5)

    assert result.format == "json"
    assert result.row_count_estimate == 2
    assert result.columns[0].name == "label"
    assert result.columns[0].dtype == "int"
    assert result.sample_rows[1]["city"] == "Busan"
    assert result.suggested_target is not None
    assert result.suggested_target.column_name == "label"


def test_preview_uploaded_file_excel_supports_first_sheet(tmp_path) -> None:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")

    workbook = Path(tmp_path) / "book.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame({"note": ["metadata"]}).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(
            {
                "target": [0, 1, 0],
                "age": [31, 45, 28],
                "country": ["KR", "US", "JP"],
            }
        ).to_excel(writer, sheet_name="Modeling", index=False)

    result = PreviewUploadedFileUseCase(str(tmp_path)).execute("book.xlsx", head_rows=1000)

    assert result.format == "excel"
    assert result.row_count_estimate == 1
    assert [column.name for column in result.columns] == ["note"]
    assert result.sample_rows[0]["note"] == "metadata"


def test_preview_uploaded_file_parquet_supports_head_preview(tmp_path) -> None:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")

    parquet_path = Path(tmp_path) / "signals.parquet"
    pd.DataFrame(
        {
            "default": [0, 1, 0, 1],
            "utilization": [0.2, 0.5, 0.7, 0.9],
            "region": ["KR", "KR", "US", "JP"],
        }
    ).to_parquet(parquet_path)

    result = PreviewUploadedFileUseCase(str(tmp_path)).execute("signals.parquet", head_rows=2)

    assert result.format == "parquet"
    assert result.row_count_estimate is None
    assert len(result.sample_rows) == 2
    assert result.columns[0].name == "default"
    assert result.suggested_target is not None
    assert result.suggested_target.column_name == "default"


def test_preview_uploaded_file_lowers_confidence_for_close_candidates(
    tmp_path,
    usecase: PreviewUploadedFileUseCase,
) -> None:
    path = Path(tmp_path) / "ambiguous.csv"
    path.write_text(
        "\n".join(
            [
                "label,churn,id",
                "0,1,100",
                "1,0,101",
                "0,1,102",
                "1,0,103",
            ]
        ),
        encoding="utf-8",
    )

    result = usecase.execute("ambiguous.csv")

    assert result.suggested_target is not None
    assert result.suggested_target.column_name in {"label", "churn"}
    assert result.suggested_target.confidence == "low"


def test_preview_uploaded_file_skips_non_positive_target_signal(
    tmp_path,
    usecase: PreviewUploadedFileUseCase,
) -> None:
    path = Path(tmp_path) / "events.csv"
    path.write_text(
        "\n".join(
            [
                "event_id,event_time,customer_id",
                "1,2026-04-01T00:00:00,100",
                "2,2026-04-01T01:00:00,101",
                "3,2026-04-01T02:00:00,102",
            ]
        ),
        encoding="utf-8",
    )

    result = usecase.execute("events.csv")

    assert result.suggested_target is None
