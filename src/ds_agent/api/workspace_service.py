"""Workspace service — file listing and project management.

Extracted from AppState (4.1.4 god object decomposition).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from ds_agent.memory.project_store import ProjectStore

logger = structlog.get_logger()


class WorkspaceService:
    """Manages workspace file operations and project lifecycle."""

    _MAX_LISTED_FILES: int = 500
    _HIDDEN_ROOTS: frozenset[str] = frozenset({".ds-agent"})

    def __init__(self, workspace_dir: str) -> None:
        self._workspace_dir = workspace_dir
        self._project_store: ProjectStore | None = None

    def list_files(self, project_id: str | None = None) -> list[dict]:
        """List files in workspace or project directory.

        Each entry has: ``name``, ``path`` (relative, POSIX), ``size`` (bytes),
        ``type`` (extension without dot), ``modifiedAt`` (ms since epoch).
        The frontend uses ``modifiedAt`` for sort-by-date and "x minutes ago"
        labels — without it, users can't tell which artifacts are current vs
        stale when multiple training runs accumulate.
        """
        workspace = Path(self._workspace_dir).expanduser().resolve()
        base = workspace

        if project_id:
            # SEC: Reject obvious traversal attempts in project_id
            if ".." in project_id or project_id.startswith(("/", "\\")):
                return []
            projects_root = (workspace / "projects").resolve()
            base = self._get_project_store().get_project_dir(project_id).resolve()
            # SEC: Verify resolved path is still within workspace
            if not base.is_relative_to(projects_root):
                return []

        if not base.exists():
            return []

        # 4.9 fix: stop early once limit reached; sort afterwards
        files = []
        for f in base.rglob("*"):
            if f.is_file():
                relative_path = f.relative_to(base)
                if relative_path.parts and relative_path.parts[0] in self._HIDDEN_ROOTS:
                    continue
                stat = f.stat()
                files.append(
                    {
                        "name": f.name,
                        "path": relative_path.as_posix(),
                        "size": stat.st_size,
                        "type": f.suffix.lstrip("."),
                        "modifiedAt": int(stat.st_mtime * 1000),
                    }
                )
                if len(files) >= self._MAX_LISTED_FILES:
                    logger.warning("file_list_truncated", limit=self._MAX_LISTED_FILES)
                    break
        return sorted(files, key=lambda x: x["path"])

    # -- Delete / preview ------------------------------------------------------

    def delete_path(self, rel_path: str) -> dict:
        """Delete one file or one empty directory inside the workspace.

        Enforces workspace containment (no path traversal). Refuses to delete
        a non-empty directory so users can't nuke training results with one
        misclick — the frontend should confirm once per file and delete
        recursively itself if the user really wants that.
        """
        if not rel_path or rel_path in (".", ".."):
            raise ValueError("Invalid path")

        workspace = Path(self._workspace_dir).expanduser().resolve()
        target = (workspace / rel_path).resolve()

        if not target.is_relative_to(workspace):
            raise ValueError("Path escapes workspace")
        if target == workspace:
            raise ValueError("Refusing to delete the workspace root")
        if not target.exists():
            raise FileNotFoundError(f"No such path: {rel_path}")

        if target.is_file():
            target.unlink()
            kind = "file"
        elif target.is_dir():
            # Only remove empty directories — recursive delete is dangerous
            # and better done one-file-at-a-time from the UI.
            try:
                target.rmdir()
            except OSError as e:
                raise ValueError(f"Directory not empty: {rel_path}") from e
            kind = "directory"
        else:
            raise ValueError(f"Unsupported path type: {rel_path}")

        return {"path": rel_path, "kind": kind}

    # P1-12: per-workspace exports dir. Uses the hidden ``.ds-agent`` root
    # so regular file listings don't surface intermediate artifacts.
    _EXPORTS_DIRNAME: str = ".ds-agent"
    _EXPORTS_SUBDIR: str = "exports"

    def export_path(
        self,
        rel_path: str,
        export_format: str,
        audience: str | None = None,
    ) -> dict:
        """Export a workspace file to another format (P1-12).

        Writes the rendered file under ``<workspace>/.ds-agent/exports/<uuid>``
        and returns an absolute path. The caller (Electron main) then copies
        the file to the user's chosen location via a save dialog and is
        responsible for cleaning up the staging copy.
        """
        import uuid

        from ds_agent.infrastructure.artifact.exporters import (
            ExportError,
            ExportFormat,
            export_file,
        )

        if not rel_path:
            raise ValueError("Invalid path")

        try:
            target_format = ExportFormat(export_format)
        except ValueError as e:
            raise ValueError(f"Unsupported export format: {export_format}") from e

        workspace = Path(self._workspace_dir).expanduser().resolve()
        source = (workspace / rel_path).resolve()
        if not source.is_relative_to(workspace):
            raise ValueError("Path escapes workspace")
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"No such file: {rel_path}")

        # Refuse paths that would leak generated files back into the exports
        # dir recursively — not dangerous, just confusing.
        if self._EXPORTS_DIRNAME in source.parts:
            raise ValueError("Cannot export files from the exports directory")

        staging_root = workspace / self._EXPORTS_DIRNAME / self._EXPORTS_SUBDIR
        staging_dir = staging_root / uuid.uuid4().hex
        staging_dir.mkdir(parents=True, exist_ok=True)

        ext = "pdf" if target_format == ExportFormat.PDF else target_format.value
        audience_suffix = f".{audience}" if audience else ""
        # PDF emits an intermediate .html which Electron prints to PDF.
        if target_format == ExportFormat.PDF:
            output_name = f"{source.stem}{audience_suffix}.pdf.html"
        else:
            output_name = f"{source.stem}{audience_suffix}.{ext}"
        output_path = staging_dir / output_name

        try:
            result = export_file(source, output_path, target_format)
        except ExportError as e:
            raise ValueError(str(e)) from e

        # Containment assertion: verify the exporter did not write outside the
        # staging root we created.  This is defence-in-depth — the staging_dir
        # is already confined, but an exporter bug could theoretically produce a
        # symlink or redirect the output.  Raise hard rather than return an
        # unconfined path to the Electron layer.
        if not result.output_path.is_relative_to(staging_root):
            raise RuntimeError(
                f"Export output escaped staging root: {result.output_path}"
            )

        return {
            "exportPath": str(result.output_path),
            "format": target_format.value,
            "size": result.output_path.stat().st_size,
            "needsPdfRender": result.intermediate_html_path is not None,
            "suggestedFilename": f"{source.stem}{audience_suffix}.{ext}",
            "audience": audience,
        }

    # Text formats we're willing to dump as plain preview.
    _TEXT_EXTENSIONS: frozenset[str] = frozenset(
        {".md", ".txt", ".log", ".json", ".yaml", ".yml", ".toml", ".py", ".ini"}
    )
    _TABULAR_EXTENSIONS: frozenset[str] = frozenset(
        {".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".pq", ".json"}
    )
    _DELIMITED_ENCODINGS: tuple[str, ...] = ("utf-8", "utf-8-sig", "cp949", "euc-kr")
    _PREVIEW_MAX_BYTES: int = 256 * 1024  # 256 KB — enough for reports

    def preview_path(
        self,
        rel_path: str,
        rows: int = 20,
        *,
        sheet_name: str | None = None,
        header_row: int = 1,
    ) -> dict:
        """Return a safe preview of a file.

        CSV/TSV → columns + first ``rows`` rows (pandas). Text → truncated
        content. Anything else → metadata only. Never executes user code.
        """
        if not rel_path:
            raise ValueError("Invalid path")

        workspace = Path(self._workspace_dir).expanduser().resolve()
        target = (workspace / rel_path).resolve()

        if not target.is_relative_to(workspace):
            raise ValueError("Path escapes workspace")
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"No such file: {rel_path}")

        stat = target.stat()
        suffix = target.suffix.lower()
        meta = {
            "path": rel_path,
            "name": target.name,
            "size": stat.st_size,
            "modifiedAt": int(stat.st_mtime * 1000),
            "type": suffix.lstrip("."),
        }

        # Clamp rows so an LLM or frontend can't ask for 1M.
        rows = max(1, min(int(rows or 20), 200))
        header_row = max(1, min(int(header_row or 1), 50))

        if suffix in self._TABULAR_EXTENSIONS:
            preview = self._preview_tabular_path(
                target,
                meta,
                rows,
                sheet_name=sheet_name,
                header_row=header_row,
            )
            if preview is not None:
                return preview

        if suffix in self._TEXT_EXTENSIONS:
            try:
                text = target.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return {**meta, "kind": "error", "error": str(e)}
            truncated = len(text) > self._PREVIEW_MAX_BYTES
            if truncated:
                text = text[: self._PREVIEW_MAX_BYTES]
            return {
                **meta,
                "kind": "text",
                "content": text,
                "truncated": truncated,
            }

        # Binary / unknown — just metadata.
        return {**meta, "kind": "binary"}

    def _preview_tabular_path(
        self,
        target: Path,
        meta: dict[str, object],
        rows: int,
        *,
        sheet_name: str | None = None,
        header_row: int = 1,
    ) -> dict | None:
        suffix = target.suffix.lower()
        if suffix in {".csv", ".tsv"}:
            separator = "\t" if suffix == ".tsv" else ","
            return self._preview_delimited_file(
                target, meta, rows, separator, header_row=header_row
            )
        if suffix in {".xlsx", ".xls"}:
            return self._preview_excel_file(
                target,
                meta,
                rows,
                sheet_name=sheet_name,
                header_row=header_row,
            )
        if suffix in {".parquet", ".pq"}:
            return self._preview_parquet_file(target, meta, rows)
        if suffix == ".json":
            return self._preview_json_file(target, meta, rows)
        return None

    def _preview_delimited_file(
        self,
        target: Path,
        meta: dict[str, object],
        rows: int,
        separator: str,
        *,
        header_row: int,
    ) -> dict:
        try:
            import pandas as pd
        except ImportError:
            return {**meta, "kind": "unknown", "message": "pandas not installed"}

        df: Any | None = None
        encoding_detected: str | None = None
        last_error: Exception | None = None
        for encoding in self._DELIMITED_ENCODINGS:
            try:
                df = pd.read_csv(
                    target,
                    nrows=rows,
                    sep=separator,
                    encoding=encoding,
                    header=header_row - 1,
                )
                encoding_detected = "EUC-KR" if encoding in {"cp949", "euc-kr"} else "UTF-8"
                break
            except UnicodeDecodeError as exc:
                last_error = exc
            except Exception as exc:
                return {**meta, "kind": "error", "error": f"{type(exc).__name__}: {exc}"}

        if df is None:
            message = "Unable to decode file."
            if last_error is not None:
                message = f"{type(last_error).__name__}: {last_error}"
            return {**meta, "kind": "error", "error": message}

        try:
            with target.open("rb") as fh:
                total_rows = max(0, sum(1 for _ in fh) - header_row)
        except OSError:
            total_rows = None

        return self._build_table_preview(
            meta,
            df,
            total_rows=total_rows,
            encoding_detected=encoding_detected,
            header_row=header_row,
        )

    def _preview_excel_file(
        self,
        target: Path,
        meta: dict[str, object],
        rows: int,
        *,
        sheet_name: str | None,
        header_row: int,
    ) -> dict:
        try:
            import pandas as pd
        except ImportError:
            return {**meta, "kind": "unknown", "message": "pandas not installed"}

        try:
            workbook = pd.ExcelFile(target)
            sheet_names = [str(name) for name in workbook.sheet_names]
            if not sheet_names:
                return {**meta, "kind": "error", "error": "Workbook has no sheets."}
            selected_sheet = sheet_name or sheet_names[0]
            if selected_sheet not in sheet_names:
                return {**meta, "kind": "error", "error": f"Unknown sheet: {selected_sheet}"}
            df = workbook.parse(selected_sheet, nrows=rows, header=header_row - 1)
        except Exception as exc:
            return {**meta, "kind": "error", "error": f"{type(exc).__name__}: {exc}"}

        return self._build_table_preview(
            meta,
            df,
            total_rows=None,
            selected_sheet=selected_sheet,
            sheet_names=sheet_names,
            header_row=header_row,
        )

    def _preview_parquet_file(self, target: Path, meta: dict[str, object], rows: int) -> dict:
        try:
            import pandas as pd
        except ImportError:
            return {**meta, "kind": "unknown", "message": "pandas not installed"}

        try:
            df = pd.read_parquet(target).head(rows)
        except Exception as exc:
            return {**meta, "kind": "error", "error": f"{type(exc).__name__}: {exc}"}

        return self._build_table_preview(meta, df, total_rows=None)

    def _preview_json_file(self, target: Path, meta: dict[str, object], rows: int) -> dict | None:
        try:
            import pandas as pd
        except ImportError:
            return None

        try:
            raw = json.loads(target.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None

        try:
            if isinstance(raw, list) and all(isinstance(item, dict) for item in raw[:50]):
                total_rows = len(raw)
                df = pd.DataFrame(raw[:rows])
            elif (
                isinstance(raw, dict)
                and raw
                and all(isinstance(value, list) for value in raw.values())
            ):
                full_df = pd.DataFrame(raw)
                total_rows = len(full_df)
                df = full_df.head(rows)
            else:
                return None
        except Exception as exc:
            return {**meta, "kind": "error", "error": f"{type(exc).__name__}: {exc}"}

        return self._build_table_preview(
            meta,
            df,
            total_rows=total_rows,
            encoding_detected="UTF-8",
        )

    def _build_table_preview(
        self,
        meta: dict[str, object],
        df: Any,
        *,
        total_rows: int | None,
        encoding_detected: str | None = None,
        selected_sheet: str | None = None,
        sheet_names: list[str] | None = None,
        header_row: int = 1,
    ) -> dict:
        normalized_df = df.fillna("")
        row_count = total_rows if total_rows is not None else len(df)
        return {
            **meta,
            "kind": "table",
            "columns": [str(column) for column in df.columns],
            "rows": normalized_df.astype(str).values.tolist(),
            "previewRows": len(df),
            "totalRows": total_rows,
            "rowCount": row_count,
            "fileSizeMb": round(float(meta["size"]) / (1024 * 1024), 2),
            "encodingDetected": encoding_detected,
            "selectedSheet": selected_sheet,
            "sheetNames": sheet_names or [],
            "headerRow": header_row,
            "columnProfiles": self._build_column_profiles(df),
        }

    def _build_column_profiles(self, df: Any) -> list[dict[str, object]]:
        profiles: list[dict[str, object]] = []
        for column in df.columns:
            series = df[column]
            non_null = series.dropna()
            sample_values: list[str] = []
            seen: set[str] = set()
            for value in non_null.tolist():
                text = str(value)
                if not text or text in seen:
                    continue
                sample_values.append(text)
                seen.add(text)
                if len(sample_values) >= 3:
                    break

            profiles.append(
                {
                    "name": str(column),
                    "dtype": str(series.dtype),
                    "nullCount": int(series.isna().sum()),
                    "uniqueCount": int(non_null.nunique(dropna=True)),
                    "sampleValues": sample_values,
                }
            )
        return profiles

    def list_projects(self) -> list[dict]:
        store = self._get_project_store()
        return store.list_projects()

    def create_project(self, name: str, task_type: str | None = None) -> str:
        store = self._get_project_store()
        return store.create_project(name=name, task_type=task_type)

    def get_project(self, project_id: str) -> dict | None:
        """Return one project's metadata, if it exists."""
        store = self._get_project_store()
        return store.get_project(project_id)

    def get_project_dir(self, project_id: str) -> Path:
        """Return the absolute project directory path."""
        store = self._get_project_store()
        return store.get_project_dir(project_id).resolve()

    def resolve_project_file(self, project_id: str, rel_path: str) -> Path:
        """Resolve one project-local file path with containment checks."""
        if not rel_path:
            raise ValueError("Invalid path")
        project_dir = self.get_project_dir(project_id)
        target = (project_dir / rel_path).resolve()
        if not target.is_relative_to(project_dir):
            raise ValueError("Path escapes project workspace")
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"No such project file: {rel_path}")
        return target

    def _get_project_store(self) -> ProjectStore:
        if self._project_store is None:
            from ds_agent.memory.project_store import ProjectStore

            self._project_store = ProjectStore(str(Path(self._workspace_dir) / "projects"))
        return self._project_store
