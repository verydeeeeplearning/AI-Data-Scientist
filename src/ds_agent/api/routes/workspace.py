"""Workspace upload endpoints for drag-and-drop schema preview."""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from ds_agent.api.dependencies import require_resource_access
from ds_agent.application.usecases.preview_uploaded_file_usecase import PreviewUploadedFileUseCase

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

_MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024
_UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
_SIGNATURE_PROBE_BYTES = 512
_ALLOWED_UPLOAD_EXTENSIONS = frozenset(
    {
        ".csv",
        ".json",
        ".jsonl",
        ".parquet",
        ".pq",
        ".xlsx",
        ".xls",
    }
)
_TEXT_UPLOAD_EXTENSIONS = frozenset({".csv", ".json", ".jsonl"})
_ZIP_SIGNATURE = b"PK\x03\x04"
_OLE_SIGNATURE = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_PARQUET_SIGNATURE = b"PAR1"
_REJECTED_TEXT_SIGNATURES = (b"MZ", b"\x7fELF")


@router.post(
    "/upload",
    dependencies=[
        Depends(
            require_resource_access(
                resource_type="workspace_file",
                action="mutate",
                resource_id_extractor=lambda req: "workspace",
            )
        )
    ],
)
async def upload_workspace_file(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    head_rows: Annotated[int, Query(alias="headRows", ge=1, le=5000)] = 1000,
    sample_rows: Annotated[int, Query(alias="sampleRows", ge=1, le=20)] = 5,
) -> dict[str, Any]:
    """Persist one uploaded file and return its schema preview."""

    state: AppState = request.app.state.app_state
    workspace = Path(state.config.agent.workspace_dir).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    filename = _normalize_upload_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {extension}")

    partial_path = workspace / f".upload-{uuid.uuid4().hex}.part"
    final_path: Path | None = None
    first_bytes = b""
    total_bytes = 0

    try:
        with partial_path.open("xb") as handle:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                if not first_bytes:
                    first_bytes = chunk[:_SIGNATURE_PROBE_BYTES]
                total_bytes += len(chunk)
                if total_bytes > _MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File too large: {total_bytes} bytes "
                            f"(max {_MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB)"
                        ),
                    )
                handle.write(chunk)

        if total_bytes <= 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        _validate_upload_signature(filename, first_bytes)

        final_path = _resolve_destination_path(workspace, filename)
        partial_path.replace(final_path)
        workspace_path = final_path.relative_to(workspace).as_posix()
        preview = await asyncio.to_thread(
            PreviewUploadedFileUseCase(str(workspace)).execute,
            workspace_path,
            mime_type=_resolve_mime_type(file, filename),
            head_rows=head_rows,
            sample_rows=sample_rows,
        )
        return {"preview": preview.model_dump(mode="json", by_alias=True)}
    except HTTPException:
        _cleanup_path(partial_path)
        if final_path is not None:
            _cleanup_path(final_path)
        raise
    except ValueError as exc:
        _cleanup_path(partial_path)
        if final_path is not None:
            _cleanup_path(final_path)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()


def _normalize_upload_filename(raw_filename: str | None) -> str:
    name = str(raw_filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Filename is required")
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid filename: path separators not allowed")
    return Path(name).name


def _validate_upload_signature(filename: str, head_bytes: bytes) -> None:
    extension = Path(filename).suffix.lower()
    if extension in _TEXT_UPLOAD_EXTENSIONS:
        if b"\x00" in head_bytes:
            raise ValueError("Text uploads must not contain binary NUL bytes")
        if any(head_bytes.startswith(signature) for signature in _REJECTED_TEXT_SIGNATURES):
            raise ValueError("File signature does not match the declared text format")
        return
    if extension == ".xlsx" and not head_bytes.startswith(_ZIP_SIGNATURE):
        raise ValueError("File signature does not match the declared Excel format")
    if extension == ".xls" and not head_bytes.startswith(_OLE_SIGNATURE):
        raise ValueError("File signature does not match the declared Excel format")
    if extension in {".parquet", ".pq"} and not head_bytes.startswith(_PARQUET_SIGNATURE):
        raise ValueError("File signature does not match the declared Parquet format")


def _resolve_destination_path(workspace: Path, filename: str) -> Path:
    base = Path(filename)
    stem = base.stem
    suffix = base.suffix
    candidate = (workspace / filename).resolve()
    index = 1
    while candidate.exists():
        candidate = (workspace / f"{stem}-{index}{suffix}").resolve()
        index += 1
    if not candidate.is_relative_to(workspace):
        raise HTTPException(status_code=400, detail="Invalid upload destination")
    return candidate


def _resolve_mime_type(file: UploadFile, filename: str) -> str:
    if file.content_type and file.content_type != "application/octet-stream":
        return file.content_type
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _cleanup_path(target: Path) -> None:
    try:
        if target.exists():
            target.unlink()
    except OSError:
        return
