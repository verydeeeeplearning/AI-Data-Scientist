"""Integration test: ToolRegistry with real tool modules."""

import importlib

import pytest

from ds_agent.tools.registry import ToolRegistry


def _ensure_tools_loaded():
    """Import tool modules to trigger self-registration."""
    for module_name in [
        "ds_agent.tools.code_execution",
        "ds_agent.tools.data_loader",
        "ds_agent.tools.data_profiler",
        "ds_agent.tools.describe_table_trust",
        "ds_agent.tools.file_ops",
        "ds_agent.tools.lookup_term",
        "ds_agent.tools.load_semantic_pack",
        "ds_agent.tools.schema_tools",
        "ds_agent.tools.semantic_query",
        "ds_agent.tools.sql_tools",
        "ds_agent.tools.standing_order_tools",
    ]:
        importlib.import_module(module_name)


# Load once at module level
_ensure_tools_loaded()


class TestRegistryWithRealTools:
    def test_all_core_tools_registered(self):
        names = ToolRegistry.list_tools()
        assert "execute_code" in names
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names
        assert "data_loader" in names
        assert "data_profiler" in names
        assert "schema_inspect" in names
        assert "sql_query" in names
        assert "semantic_query" in names
        assert "lookup_term" in names
        assert "describe_table_trust" in names
        assert "load_semantic_pack" in names
        assert "standing_order" in names

    def test_schemas_valid_openai_format(self):
        defs = ToolRegistry.get_definitions()
        for d in defs:
            assert d["type"] == "function"
            assert "name" in d["function"]
            assert "description" in d["function"]
            assert "parameters" in d["function"]
            params = d["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params

    def test_ds_category_filter(self):
        ds_tools = ToolRegistry.list_tools(category="ds_analysis")
        assert "data_loader" in ds_tools
        assert "data_profiler" in ds_tools
        assert "schema_inspect" in ds_tools
        assert "sql_query" in ds_tools
        assert "semantic_query" in ds_tools
        assert "lookup_term" in ds_tools
        assert "describe_table_trust" in ds_tools
        assert "standing_order" in ds_tools
        assert "execute_code" not in ds_tools  # utility category

    @pytest.mark.asyncio
    async def test_dispatch_execute_code(self):
        result = await ToolRegistry.dispatch("execute_code", {"code": "print(2+2)"})
        assert "4" in result

    @pytest.mark.asyncio
    async def test_dispatch_read_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = await ToolRegistry.dispatch("read_file", {"file_path": str(test_file)})
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_dispatch_write_file(self, tmp_path):
        file_path = str(tmp_path / "output.txt")
        result = await ToolRegistry.dispatch(
            "write_file", {"file_path": file_path, "content": "test content"}
        )
        assert "success" in result

    @pytest.mark.asyncio
    async def test_dispatch_list_files(self, tmp_path):
        (tmp_path / "a.csv").write_text("x")
        (tmp_path / "b.csv").write_text("y")

        result = await ToolRegistry.dispatch(
            "list_files", {"directory": str(tmp_path), "pattern": "*.csv"}
        )
        assert '"count": 2' in result
