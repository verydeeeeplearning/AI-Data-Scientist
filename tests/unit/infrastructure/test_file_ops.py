"""Tests for tools/file_ops.py — read, write, list operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ds_agent.tools.file_ops import list_files, read_file, write_file


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        result = await read_file(str(f))
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_read_missing_file(self):
        result = await read_file("/nonexistent/path/to/file.txt")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower() or "File not found" in parsed["error"]

    @pytest.mark.asyncio
    async def test_read_with_head_lines(self, tmp_path: Path):
        f = tmp_path / "multi.txt"
        f.write_text("line1\nline2\nline3\nline4\nline5", encoding="utf-8")
        result = await read_file(str(f), head_lines=2)
        assert "line1" in result
        assert "line2" in result
        assert "... (5 total lines)" in result
        lines = result.split("\n")
        assert lines[0] == "line1"
        assert lines[1] == "line2"

    @pytest.mark.asyncio
    async def test_read_with_head_lines_none(self, tmp_path: Path):
        f = tmp_path / "full.txt"
        f.write_text("a\nb\nc", encoding="utf-8")
        result = await read_file(str(f), head_lines=None)
        assert result == "a\nb\nc"

    @pytest.mark.asyncio
    async def test_read_binary_file_errors_gracefully(self, tmp_path: Path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        # Should not crash — errors="replace" handles it
        result = await read_file(str(f))
        assert isinstance(result, str)


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write_creates_file(self, tmp_path: Path):
        target = tmp_path / "output.txt"
        result = await write_file(str(target), "hello")
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["bytes"] == 5
        assert target.read_text(encoding="utf-8") == "hello"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, tmp_path: Path):
        target = tmp_path / "sub" / "deep" / "file.txt"
        result = await write_file(str(target), "nested content")
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "nested content"

    @pytest.mark.asyncio
    async def test_write_error_on_invalid_path(self):
        # Attempt to write to a path that can't work (null byte in name)
        result = await write_file("/\x00invalid", "data")
        parsed = json.loads(result)
        assert "error" in parsed


class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_existing_directory(self, tmp_path: Path):
        (tmp_path / "a.csv").write_text("a", encoding="utf-8")
        (tmp_path / "b.csv").write_text("b", encoding="utf-8")
        (tmp_path / "c.txt").write_text("c", encoding="utf-8")

        result = await list_files(str(tmp_path))
        parsed = json.loads(result)
        assert parsed["count"] == 3
        assert len(parsed["files"]) == 3

    @pytest.mark.asyncio
    async def test_list_with_pattern(self, tmp_path: Path):
        (tmp_path / "a.csv").write_text("a", encoding="utf-8")
        (tmp_path / "b.csv").write_text("b", encoding="utf-8")
        (tmp_path / "c.txt").write_text("c", encoding="utf-8")

        result = await list_files(str(tmp_path), pattern="*.csv")
        parsed = json.loads(result)
        assert parsed["count"] == 2

    @pytest.mark.asyncio
    async def test_list_nonexistent_directory(self):
        result = await list_files("/nonexistent/dir/abc123")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower() or "Directory not found" in parsed["error"]

    @pytest.mark.asyncio
    async def test_list_empty_directory(self, tmp_path: Path):
        result = await list_files(str(tmp_path))
        parsed = json.loads(result)
        assert parsed["count"] == 0
        assert parsed["files"] == []
