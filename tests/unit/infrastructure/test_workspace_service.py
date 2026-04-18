"""Tests for WorkspaceService — extracted from AppState (4.1.4)."""

from __future__ import annotations

import pytest

from ds_agent.api.workspace_service import WorkspaceService


@pytest.fixture
def workspace(tmp_path: object) -> WorkspaceService:
    return WorkspaceService(str(tmp_path))


class TestWorkspaceService:
    def test_list_files_empty_workspace(self, workspace: WorkspaceService) -> None:
        files = workspace.list_files()
        assert files == []

    def test_list_files_with_files(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        p = Path(str(tmp_path))
        (p / "test.csv").write_text("a,b,c")
        (p / "data.json").write_text("{}")

        files = workspace.list_files()
        assert len(files) == 2
        names = {f["name"] for f in files}
        assert names == {"test.csv", "data.json"}

    def test_list_files_path_traversal_rejected(self, workspace: WorkspaceService) -> None:
        files = workspace.list_files("../../etc")
        assert files == []

    def test_list_files_nonexistent_project(self, workspace: WorkspaceService) -> None:
        files = workspace.list_files("nonexistent-project")
        assert files == []

    def test_list_files_project_reads_from_projects_directory(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        p = Path(str(tmp_path))
        project_id = workspace.create_project("demo")
        artifact = p / "projects" / project_id / "artifacts" / "model.pkl"
        artifact.write_text("binary-ish")

        files = workspace.list_files(project_id)

        assert len(files) == 2
        paths = {f["path"] for f in files}
        assert "artifacts/model.pkl" in paths
        assert "meta.json" in paths

    def test_list_files_capped_at_max(self, tmp_path: object) -> None:
        from pathlib import Path

        p = Path(str(tmp_path))
        for i in range(600):
            (p / f"file_{i:04d}.txt").write_text(f"content {i}")

        ws = WorkspaceService(str(tmp_path))
        files = ws.list_files()
        assert len(files) == 500

    def test_list_files_returns_relative_paths(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        p = Path(str(tmp_path))
        sub = p / "subdir"
        sub.mkdir()
        (sub / "nested.csv").write_text("data")

        files = workspace.list_files()
        assert len(files) == 1
        # Path should be relative to workspace, not absolute
        assert "/" not in files[0]["path"] or files[0]["path"].startswith("subdir")

    def test_list_files_includes_modified_at(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "a.csv").write_text("x,y\n1,2")
        files = workspace.list_files()
        assert len(files) == 1
        assert "modifiedAt" in files[0]
        assert isinstance(files[0]["modifiedAt"], int)
        assert files[0]["modifiedAt"] > 0


class TestDeletePath:
    def test_delete_file(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        p = Path(str(tmp_path)) / "scratch.csv"
        p.write_text("hi")
        result = workspace.delete_path("scratch.csv")
        assert result == {"path": "scratch.csv", "kind": "file"}
        assert not p.exists()

    def test_delete_nested_file(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        sub = Path(str(tmp_path)) / "eda"
        sub.mkdir()
        (sub / "plot.png").write_bytes(b"\x89PNG")
        workspace.delete_path("eda/plot.png")
        assert not (sub / "plot.png").exists()
        assert sub.exists()  # parent directory preserved

    def test_delete_empty_directory(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "empty").mkdir()
        result = workspace.delete_path("empty")
        assert result["kind"] == "directory"
        assert not (Path(str(tmp_path)) / "empty").exists()

    def test_delete_non_empty_directory_refused(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        sub = Path(str(tmp_path)) / "full"
        sub.mkdir()
        (sub / "x.txt").write_text("x")
        with pytest.raises(ValueError, match="not empty"):
            workspace.delete_path("full")

    def test_delete_missing_path_raises(self, workspace: WorkspaceService) -> None:
        with pytest.raises(FileNotFoundError):
            workspace.delete_path("does_not_exist.csv")

    def test_delete_path_traversal_rejected(self, workspace: WorkspaceService) -> None:
        with pytest.raises(ValueError, match="escapes workspace"):
            workspace.delete_path("../../etc/passwd")

    def test_delete_refuses_workspace_root(self, workspace: WorkspaceService) -> None:
        with pytest.raises(ValueError):
            workspace.delete_path(".")


class TestPreviewPath:
    def test_preview_csv(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        csv = Path(str(tmp_path)) / "t.csv"
        csv.write_text("a,b,c\n1,2,3\n4,5,6\n7,8,9\n")

        result = workspace.preview_path("t.csv", rows=2)
        assert result["kind"] == "table"
        assert result["columns"] == ["a", "b", "c"]
        assert result["previewRows"] == 2
        assert result["totalRows"] == 3  # three data rows
        assert result["rows"][0] == ["1", "2", "3"]
        assert result["rowCount"] == 3
        assert result["encodingDetected"] == "UTF-8"
        assert result["columnProfiles"][0]["name"] == "a"
        assert result["columnProfiles"][0]["dtype"] == "int64"

    def test_preview_csv_with_nulls(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        csv = Path(str(tmp_path)) / "n.csv"
        csv.write_text("a,b\n1,\n,2\n")
        result = workspace.preview_path("n.csv")
        assert result["kind"] == "table"
        # NaN becomes "" so JSON stays clean
        assert all(isinstance(v, str) for row in result["rows"] for v in row)
        assert result["columnProfiles"][0]["nullCount"] == 1
        assert result["columnProfiles"][1]["nullCount"] == 1

    def test_preview_csv_with_euc_kr_encoding(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        csv = Path(str(tmp_path)) / "korean.csv"
        csv.write_bytes("city,value\n서울,1\n부산,2\n".encode("euc-kr"))

        result = workspace.preview_path("korean.csv")

        assert result["kind"] == "table"
        assert result["encodingDetected"] == "EUC-KR"
        assert result["rows"][0] == ["서울", "1"]

    def test_preview_json_table(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        payload = Path(str(tmp_path)) / "records.json"
        payload.write_text(
            '[{"customer_id": 1, "city": "Seoul"}, {"customer_id": 2, "city": "Busan"}]',
            encoding="utf-8",
        )

        result = workspace.preview_path("records.json")

        assert result["kind"] == "table"
        assert result["columns"] == ["customer_id", "city"]
        assert result["rowCount"] == 2
        assert result["encodingDetected"] == "UTF-8"

    def test_preview_excel_with_sheet_and_header_row(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        pd = pytest.importorskip("pandas")
        workbook_path = Path(str(tmp_path)) / "book.xlsx"

        with pd.ExcelWriter(workbook_path) as writer:
            pd.DataFrame({"note": ["metadata"]}).to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )
            pd.DataFrame(
                [
                    ["report generated", ""],
                    ["city", "value"],
                    ["Seoul", 10],
                    ["Busan", 20],
                ]
            ).to_excel(
                writer,
                sheet_name="Data",
                index=False,
                header=False,
            )

        result = workspace.preview_path("book.xlsx", sheet_name="Data", header_row=2)

        assert result["kind"] == "table"
        assert result["selectedSheet"] == "Data"
        assert result["headerRow"] == 2
        assert result["sheetNames"] == ["Summary", "Data"]
        assert result["columns"] == ["city", "value"]
        assert result["rows"][0] == ["Seoul", "10"]
        assert result["rowCount"] == 2

    def test_preview_markdown(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        md = Path(str(tmp_path)) / "report.md"
        md.write_text("# Report\n\nSome text")
        result = workspace.preview_path("report.md")
        assert result["kind"] == "text"
        assert result["content"].startswith("# Report")
        assert result["truncated"] is False

    def test_preview_text_truncated(self, tmp_path: object, workspace: WorkspaceService) -> None:
        from pathlib import Path

        big = Path(str(tmp_path)) / "big.log"
        big.write_text("x" * (300 * 1024))  # > 256KB
        result = workspace.preview_path("big.log")
        assert result["kind"] == "text"
        assert result["truncated"] is True
        assert len(result["content"]) == 256 * 1024

    def test_preview_binary_metadata_only(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        bin_file = Path(str(tmp_path)) / "model.joblib"
        bin_file.write_bytes(b"\x80\x04k")
        result = workspace.preview_path("model.joblib")
        assert result["kind"] == "binary"
        assert result["size"] == 3
        assert result["type"] == "joblib"

    def test_preview_path_traversal_rejected(self, workspace: WorkspaceService) -> None:
        with pytest.raises(ValueError, match="escapes workspace"):
            workspace.preview_path("../secret.txt")

    def test_preview_missing_file(self, workspace: WorkspaceService) -> None:
        with pytest.raises(FileNotFoundError):
            workspace.preview_path("nope.csv")


class TestExportPath:
    def test_export_markdown_to_html_staging(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "report.md").write_text("# Hi\n", encoding="utf-8")
        result = workspace.export_path("report.md", "html")
        exported = Path(result["exportPath"])
        assert exported.is_file()
        assert result["format"] == "html"
        assert result["needsPdfRender"] is False
        assert result["suggestedFilename"] == "report.html"
        assert ".ds-agent" in exported.parts
        assert "exports" in exported.parts

    def test_export_pdf_signals_intermediate_render(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "report.md").write_text("# Hi\n", encoding="utf-8")
        result = workspace.export_path("report.md", "pdf")
        assert result["needsPdfRender"] is True
        assert result["suggestedFilename"] == "report.pdf"
        assert Path(result["exportPath"]).suffix == ".html"

    def test_export_rejects_path_traversal(
        self, workspace: WorkspaceService
    ) -> None:
        with pytest.raises(ValueError, match="escapes workspace"):
            workspace.export_path("../etc/hosts", "html")

    def test_export_rejects_unsupported_format(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "report.md").write_text("# Hi\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported export format"):
            workspace.export_path("report.md", "exe")

    def test_export_rejects_unsupported_combination(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        (Path(str(tmp_path)) / "report.md").write_text("# Hi\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot export"):
            workspace.export_path("report.md", "xlsx")

    def test_export_missing_file_raises(
        self, workspace: WorkspaceService
    ) -> None:
        with pytest.raises(FileNotFoundError):
            workspace.export_path("nope.md", "html")

    def test_export_refuses_files_inside_exports_dir(
        self, tmp_path: object, workspace: WorkspaceService
    ) -> None:
        from pathlib import Path

        staging = Path(str(tmp_path)) / ".ds-agent" / "exports" / "abc"
        staging.mkdir(parents=True)
        (staging / "already.html").write_text("<html></html>", encoding="utf-8")
        with pytest.raises(ValueError, match="Cannot export files from the exports"):
            workspace.export_path(".ds-agent/exports/abc/already.html", "pdf")

