"""Build a head-only schema preview for one uploaded workspace file."""

from __future__ import annotations

import json
import math
import mimetypes
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from ds_agent.api.workspace_service import WorkspaceService
from ds_agent.application.dtos.schema_preview_dto import (
    ColumnInfoDTO,
    DataQualityDTO,
    SchemaPreviewDTO,
    SuggestedActionDTO,
    SuggestedTargetDTO,
)

_HEAD_ROW_LIMIT = 5_000
_SAMPLE_ROW_LIMIT = 20
_TARGET_POSITIVE_NAME_HINTS = ("target", "label", "churn", "fraud", "default")
_TARGET_NEGATIVE_NAME_HINTS = ("id", "date", "time")
_DELIMITED_ENCODINGS = ("utf-8", "utf-8-sig", "cp949", "euc-kr")
_PreviewFormat = Literal["csv", "parquet", "excel", "json", "jsonl", "unknown"]
_PreviewDtype = Literal["int", "float", "string", "datetime", "bool", "category", "unknown"]
_PreviewConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class _HeadFrameResult:
    dataframe: Any
    row_count_estimate: int | None = None


class PreviewUploadedFileUseCase:
    """Generate a schema preview from the saved uploaded file."""

    def __init__(self, workspace_dir: str) -> None:
        self._workspace_dir = str(workspace_dir)
        self._workspace = WorkspaceService(self._workspace_dir)

    def execute(
        self,
        workspace_path: str,
        *,
        mime_type: str | None = None,
        head_rows: int = 1000,
        sample_rows: int = 5,
    ) -> SchemaPreviewDTO:
        """Return a preview DTO for one workspace-local uploaded file."""
        normalized_head_rows = max(1, min(int(head_rows or 1000), _HEAD_ROW_LIMIT))
        normalized_sample_rows = max(1, min(int(sample_rows or 5), _SAMPLE_ROW_LIMIT))

        workspace_root = Path(self._workspace_dir).expanduser().resolve()
        target = (workspace_root / workspace_path).resolve()
        if not target.is_relative_to(workspace_root):
            raise ValueError("Path escapes workspace")
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"No such uploaded file: {workspace_path}")

        file_format = self._detect_format(target)
        head_result = self._load_head_dataframe(target, file_format, normalized_head_rows)
        dataframe = head_result.dataframe

        preview_meta: dict[str, object] | None = None
        if file_format in {"csv", "excel"}:
            preview_meta = self._workspace.preview_path(workspace_path, rows=normalized_sample_rows)
            preview_kind = str(preview_meta.get("kind", ""))
            if preview_kind == "error":
                raise ValueError(str(preview_meta.get("error", "Unable to preview uploaded file")))
            if preview_kind != "table":
                raise ValueError("Uploaded file is not previewable as tabular data")

        if len(dataframe.columns) == 0:
            raise ValueError("Uploaded file has no previewable columns")

        stat = target.stat()
        resolved_mime = (
            mime_type
            or mimetypes.guess_type(target.name)[0]
            or "application/octet-stream"
        )
        row_count_estimate = self._resolve_row_count_estimate(
            preview_meta,
            head_result.row_count_estimate,
            len(dataframe),
            normalized_head_rows,
        )
        suggested_target = self._suggest_target(dataframe)

        return SchemaPreviewDTO(
            fileId=workspace_path,
            workspacePath=workspace_path,
            fileName=target.name,
            sizeBytes=stat.st_size,
            mimeType=resolved_mime,
            format=file_format,
            rowCountEstimate=row_count_estimate,
            columns=self._build_columns(dataframe),
            sampleRows=self._build_sample_rows(dataframe, limit=normalized_sample_rows),
            dataQuality=self._build_data_quality(dataframe),
            suggestedTarget=suggested_target,
            suggestedActions=self._build_suggested_actions(),
        )

    @staticmethod
    def _detect_format(target: Path) -> _PreviewFormat:
        suffix = target.suffix.lower()
        if suffix == ".csv":
            return "csv"
        if suffix in {".parquet", ".pq"}:
            return "parquet"
        if suffix in {".xlsx", ".xls"}:
            return "excel"
        if suffix == ".json":
            return "json"
        if suffix == ".jsonl":
            return "jsonl"
        return "unknown"

    def _load_head_dataframe(
        self,
        target: Path,
        file_format: str,
        head_rows: int,
    ) -> _HeadFrameResult:
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - pandas is a runtime dependency here
            raise ValueError("pandas is required to preview uploaded files") from exc

        if file_format == "csv":
            return self._read_csv_head(pd, target, head_rows)
        if file_format == "excel":
            return self._read_excel_head(pd, target, head_rows)
        if file_format == "parquet":
            return self._read_parquet_head(pd, target, head_rows)
        if file_format == "json":
            return self._read_json_head(pd, target, head_rows)
        if file_format == "jsonl":
            return self._read_jsonl_head(pd, target, head_rows)
        raise ValueError(f"Unsupported preview format: {target.suffix.lower()}")

    @staticmethod
    def _read_csv_head(pd: Any, target: Path, head_rows: int) -> _HeadFrameResult:
        last_error: Exception | None = None
        for encoding in _DELIMITED_ENCODINGS:
            try:
                dataframe = pd.read_csv(target, nrows=head_rows, encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
            except Exception as exc:
                raise ValueError(
                    f"Unable to parse CSV preview: {type(exc).__name__}: {exc}"
                ) from exc
        else:
            message = "Unable to decode CSV preview."
            if last_error is not None:
                message = f"{type(last_error).__name__}: {last_error}"
            raise ValueError(message)
        row_count_estimate = len(dataframe) if len(dataframe) < head_rows else None
        return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)

    @staticmethod
    def _read_excel_head(pd: Any, target: Path, head_rows: int) -> _HeadFrameResult:
        try:
            workbook = pd.ExcelFile(target)
            if not workbook.sheet_names:
                raise ValueError("Workbook has no sheets.")
            dataframe = workbook.parse(workbook.sheet_names[0], nrows=head_rows)
        except Exception as exc:
            raise ValueError(f"Unable to parse Excel preview: {type(exc).__name__}: {exc}") from exc
        row_count_estimate = len(dataframe) if len(dataframe) < head_rows else None
        return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)

    @staticmethod
    def _read_parquet_head(pd: Any, target: Path, head_rows: int) -> _HeadFrameResult:
        try:
            import pyarrow.parquet as pq  # type: ignore[import-untyped]

            parquet_file = pq.ParquetFile(target)
            batches = parquet_file.iter_batches(batch_size=head_rows)
            first_batch = next(batches, None)
            dataframe = pd.DataFrame() if first_batch is None else first_batch.to_pandas()
        except ImportError:
            try:
                dataframe = pd.read_parquet(target).head(head_rows)
            except Exception as exc:
                raise ValueError(
                    f"Unable to parse Parquet preview: {type(exc).__name__}: {exc}"
                ) from exc
        except Exception as exc:
            raise ValueError(
                f"Unable to parse Parquet preview: {type(exc).__name__}: {exc}"
            ) from exc
        row_count_estimate = len(dataframe) if len(dataframe) < head_rows else None
        return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)

    def _read_json_head(self, pd: Any, target: Path, head_rows: int) -> _HeadFrameResult:
        records = self._stream_json_array_records(target, head_rows)
        if records is not None:
            dataframe = pd.DataFrame(records)
            row_count_estimate = len(records) if len(records) < head_rows else None
            return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)

        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Unable to parse JSON preview: {type(exc).__name__}: {exc}") from exc

        try:
            if isinstance(raw, list) and all(isinstance(item, dict) for item in raw[:50]):
                dataframe = pd.DataFrame(raw[:head_rows])
                row_count_estimate = len(raw)
                return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)
            if (
                isinstance(raw, dict)
                and raw
                and all(isinstance(value, list) for value in raw.values())
            ):
                full_dataframe = pd.DataFrame(raw)
                dataframe = full_dataframe.head(head_rows)
                row_count_estimate = len(full_dataframe)
                return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)
        except Exception as exc:
            raise ValueError(f"Unable to parse JSON preview: {type(exc).__name__}: {exc}") from exc

        raise ValueError("JSON upload must contain a top-level array of objects or object of lists")

    @staticmethod
    def _read_jsonl_head(pd: Any, target: Path, head_rows: int) -> _HeadFrameResult:
        try:
            dataframe = pd.read_json(target, lines=True, nrows=head_rows)
        except ValueError:
            try:
                rows: list[dict[str, object]] = []
                with target.open("r", encoding="utf-8") as handle:
                    for index, line in enumerate(handle):
                        if index >= head_rows:
                            break
                        stripped = line.strip()
                        if not stripped:
                            continue
                        payload = json.loads(stripped)
                        if not isinstance(payload, dict):
                            raise ValueError("JSONL preview requires object records")
                        rows.append(payload)
                dataframe = pd.DataFrame(rows)
            except Exception as exc:
                raise ValueError(
                    f"Unable to parse JSONL preview: {type(exc).__name__}: {exc}"
                ) from exc
        except Exception as exc:
            raise ValueError(f"Unable to parse JSONL preview: {type(exc).__name__}: {exc}") from exc

        row_count_estimate = len(dataframe) if len(dataframe) < head_rows else None
        return _HeadFrameResult(dataframe=dataframe, row_count_estimate=row_count_estimate)

    @staticmethod
    def _stream_json_array_records(target: Path, head_rows: int) -> list[dict[str, object]] | None:
        decoder = json.JSONDecoder()
        records: list[dict[str, object]] = []
        chunk_size = 8192
        with target.open("r", encoding="utf-8") as handle:
            buffer = ""
            started = False
            finished = False
            while not finished and len(records) < head_rows:
                chunk = handle.read(chunk_size)
                if chunk:
                    buffer += chunk
                elif not buffer:
                    break

                while True:
                    buffer = buffer.lstrip()
                    if not buffer:
                        break
                    if not started:
                        if buffer[0] != "[":
                            return None
                        started = True
                        buffer = buffer[1:]
                        continue
                    if buffer[0] == "]":
                        finished = True
                        buffer = buffer[1:]
                        break
                    if buffer[0] == ",":
                        buffer = buffer[1:]
                        continue
                    try:
                        value, index = decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        if chunk:
                            break
                        raise
                    if not isinstance(value, dict):
                        return None
                    records.append(value)
                    buffer = buffer[index:]
                    if len(records) >= head_rows:
                        break
                if not chunk:
                    break
        return records

    @staticmethod
    def _resolve_row_count_estimate(
        preview_meta: dict[str, object] | None,
        read_estimate: int | None,
        dataframe_length: int,
        head_rows: int,
    ) -> int | None:
        if read_estimate is not None:
            return int(read_estimate)
        if preview_meta is not None:
            total_rows = preview_meta.get("totalRows")
            if isinstance(total_rows, int):
                return total_rows
        if dataframe_length < head_rows:
            return int(dataframe_length)
        return None

    def _build_columns(self, dataframe: Any) -> list[ColumnInfoDTO]:
        return [
            ColumnInfoDTO(
                name=str(column),
                dtype=self._map_dtype(dataframe[column]),
                nullCount=int(dataframe[column].isna().sum()),
                uniqueCount=int(dataframe[column].dropna().nunique(dropna=True)),
                sampleValues=self._sample_values(dataframe[column]),
            )
            for column in dataframe.columns
        ]

    def _build_sample_rows(self, dataframe: Any, *, limit: int) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        sample = dataframe.head(limit)
        for _index, row in sample.iterrows():
            rows.append(
                {
                    str(column): self._normalize_value(row[column])
                    for column in sample.columns
                }
            )
        return rows

    def _build_data_quality(self, dataframe: Any) -> DataQualityDTO:
        if dataframe.empty or len(dataframe.columns) == 0:
            return DataQualityDTO(
                missingRatio=0.0,
                duplicateRowRatio=0.0,
                outlierColumns=[],
            )

        missing_ratio = float(dataframe.isna().mean().mean())
        duplicate_row_ratio = float(dataframe.duplicated().mean()) if len(dataframe) > 0 else 0.0
        outlier_columns = self._detect_outlier_columns(dataframe)
        return DataQualityDTO(
            missingRatio=round(missing_ratio, 6),
            duplicateRowRatio=round(duplicate_row_ratio, 6),
            outlierColumns=outlier_columns,
        )

    def _detect_outlier_columns(self, dataframe: Any) -> list[str]:
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - guarded higher up
            return []

        outliers: list[str] = []
        numeric_columns = dataframe.select_dtypes(include=["number"]).columns
        for column in numeric_columns:
            series = dataframe[column]
            if pd.api.types.is_bool_dtype(series):
                continue
            non_null = series.dropna()
            if len(non_null) < 4:
                continue
            q1 = float(non_null.quantile(0.25))
            q3 = float(non_null.quantile(0.75))
            iqr = q3 - q1
            if math.isclose(iqr, 0.0):
                continue
            lower = q1 - (1.5 * iqr)
            upper = q3 + (1.5 * iqr)
            ratio = float(((non_null < lower) | (non_null > upper)).mean())
            if ratio > 0.01:
                outliers.append(str(column))
        return outliers

    def _suggest_target(self, dataframe: Any) -> SuggestedTargetDTO | None:
        ranked: list[tuple[int, str, str]] = []
        for column in dataframe.columns:
            series = dataframe[column]
            score = 0
            reasons: list[str] = []
            lower_name = str(column).lower()
            tokens = {
                token
                for token in re.split(r"[^a-z0-9]+", lower_name)
                if token
            }

            if any(hint in lower_name for hint in _TARGET_POSITIVE_NAME_HINTS) or "y" in tokens:
                score += 3
                reasons.append("name_hint")
            if int(series.dropna().nunique(dropna=True)) == 2:
                score += 2
                reasons.append("binary_values")
            if any(hint in lower_name for hint in _TARGET_NEGATIVE_NAME_HINTS):
                score -= 3
                reasons.append("identifier_or_time_like")

            null_ratio = float(series.isna().mean()) if len(series) else 0.0
            if null_ratio > 0.30:
                score -= 2
                reasons.append("high_null_ratio")

            mapped_dtype = self._map_dtype(series)
            non_null = series.dropna()
            unique_count = int(non_null.nunique(dropna=True))
            if mapped_dtype in {"string", "category"} and unique_count > 50:
                score -= 2
                reasons.append("high_cardinality_text")

            ranked.append((score, str(column), ", ".join(reasons) or "weak_signal"))

        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked or ranked[0][0] <= 0:
            return None

        best_score, best_column, best_reason = ranked[0]
        next_score = ranked[1][0] if len(ranked) > 1 else float("-inf")
        gap = best_score - next_score if next_score != float("-inf") else best_score

        if best_score >= 5 and gap >= 2:
            confidence: _PreviewConfidence = "high"
        elif best_score >= 3 and gap >= 1:
            confidence = "medium"
        else:
            confidence = "low"

        return SuggestedTargetDTO(
            columnName=best_column,
            confidence=confidence,
            reason=best_reason,
        )

    @staticmethod
    def _build_suggested_actions() -> list[SuggestedActionDTO]:
        return [
            SuggestedActionDTO(
                id="run_eda",
                label="workspace.upload.suggestedActions.runEda.label",
                description="workspace.upload.suggestedActions.runEda.description",
                icon="chart",
                requiresTarget=False,
            ),
            SuggestedActionDTO(
                id="baseline_after_target",
                label="workspace.upload.suggestedActions.baselineAfterTarget.label",
                description="workspace.upload.suggestedActions.baselineAfterTarget.description",
                icon="target",
                requiresTarget=True,
            ),
            SuggestedActionDTO(
                id="validate_schema",
                label="workspace.upload.suggestedActions.validateSchema.label",
                description="workspace.upload.suggestedActions.validateSchema.description",
                icon="shield",
                requiresTarget=False,
            ),
        ]

    @staticmethod
    def _map_dtype(series: Any) -> _PreviewDtype:
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - guarded higher up
            return "unknown"

        non_null = series.dropna()
        if pd.api.types.is_bool_dtype(series):
            return "bool"
        if pd.api.types.is_integer_dtype(series):
            return "int"
        if pd.api.types.is_float_dtype(series):
            if len(non_null) > 0:
                try:
                    if bool((non_null % 1 == 0).all()):
                        return "int"
                except Exception:
                    pass
            return "float"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
        if isinstance(series.dtype, pd.CategoricalDtype):
            return "category"
        if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
            unique_count = int(non_null.nunique(dropna=True))
            non_null_count = len(non_null)
            if non_null_count > 0 and unique_count <= min(20, max(1, int(non_null_count * 0.2))):
                return "category"
            return "string"
        return cast(_PreviewDtype, "unknown")

    def _sample_values(self, series: Any) -> list[object]:
        values: list[object] = []
        seen: set[str] = set()
        for value in series.dropna().tolist():
            normalized = self._normalize_value(value)
            signature = repr(normalized)
            if signature in seen:
                continue
            values.append(normalized)
            seen.add(signature)
            if len(values) >= 3:
                break
        return values

    @staticmethod
    def _normalize_value(value: object) -> object:
        if value is None:
            return None
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover - guarded higher up
            pd = None

        if pd is not None and pd.isna(value):
            return None
        if hasattr(value, "item"):
            with suppress(Exception):
                value = value.item()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)):
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                return None
            return value
        return str(value)
