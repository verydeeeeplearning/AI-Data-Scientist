"""ToolRegistry tests: registration, dispatch, schema, reset."""

import pytest

from ds_agent.tools.registry import ToolRegistry, tool


class TestToolRegistration:
    def setup_method(self):
        ToolRegistry.reset()

    def test_register_tool(self):
        @tool(name="test_tool", description="A test tool")
        async def test_tool_handler(x: int = 0) -> str:
            return f"result: {x}"

        assert "test_tool" in ToolRegistry.list_tools()

    def test_register_duplicate_raises(self):
        @tool(name="dup_tool", description="First")
        async def handler1() -> str:
            return "1"

        with pytest.raises(ValueError, match="already registered"):

            @tool(name="dup_tool", description="Second")
            async def handler2() -> str:
                return "2"

    def test_get_definitions_returns_openai_format(self):
        @tool(
            name="my_tool",
            description="Does something",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "integer", "description": "A number"}},
                "required": ["x"],
            },
        )
        async def my_handler(x: int = 0) -> str:
            return str(x)

        defs = ToolRegistry.get_definitions()
        assert len(defs) == 1
        assert defs[0]["type"] == "function"
        assert defs[0]["function"]["name"] == "my_tool"
        assert "parameters" in defs[0]["function"]

    def test_list_tools(self):
        @tool(name="tool_a", description="A")
        async def ha() -> str:
            return "a"

        @tool(name="tool_b", description="B")
        async def hb() -> str:
            return "b"

        names = ToolRegistry.list_tools()
        assert "tool_a" in names
        assert "tool_b" in names

    def test_reset_clears_all(self):
        @tool(name="temp", description="Temp")
        async def temp() -> str:
            return ""

        assert len(ToolRegistry.list_tools()) > 0
        ToolRegistry.reset()
        assert len(ToolRegistry.list_tools()) == 0


class TestToolDispatch:
    def setup_method(self):
        ToolRegistry.reset()

    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        @tool(name="add", description="Add numbers")
        async def add_handler(a: int = 0, b: int = 0) -> str:
            return str(a + b)

        result = await ToolRegistry.dispatch("add", {"a": 3, "b": 4})
        assert result == "7"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool_returns_error(self):
        result = await ToolRegistry.dispatch("nonexistent", {})
        assert "error" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_returns_error(self):
        @tool(name="failing", description="Fails")
        async def failing_handler() -> str:
            raise ValueError("Something broke")

        result = await ToolRegistry.dispatch("failing", {})
        assert "error" in result.lower()
        assert "Something broke" in result

    @pytest.mark.asyncio
    async def test_dispatch_sync_handler(self):
        """Sync handlers should also work."""

        @tool(name="sync_tool", description="Sync")
        def sync_handler(x: int = 1) -> str:
            return f"sync: {x}"

        result = await ToolRegistry.dispatch("sync_tool", {"x": 42})
        assert result == "sync: 42"


class TestToolCategories:
    def setup_method(self):
        ToolRegistry.reset()

    def test_category_assignment(self):
        @tool(name="ds_tool", description="DS", category="ds_analysis")
        async def ds() -> str:
            return ""

        @tool(name="util_tool", description="Util", category="utility")
        async def util() -> str:
            return ""

        ds_tools = ToolRegistry.list_tools(category="ds_analysis")
        assert "ds_tool" in ds_tools
        assert "util_tool" not in ds_tools
