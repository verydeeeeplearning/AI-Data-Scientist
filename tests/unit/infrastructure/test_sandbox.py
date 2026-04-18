"""ProcessSandbox tests."""

import pytest

from ds_agent.tools.sandbox import ProcessSandbox, SandboxResult


class TestProcessSandbox:
    @pytest.mark.asyncio
    async def test_execute_simple_code(self):
        sandbox = ProcessSandbox()
        result = await sandbox.execute("print('hello world')")

        assert result.success
        assert "hello world" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        sandbox = ProcessSandbox()
        result = await sandbox.execute("raise ValueError('test error')")

        assert not result.success
        assert "test error" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        sandbox = ProcessSandbox(timeout=2)
        result = await sandbox.execute("import time; time.sleep(10)")

        assert not result.success
        assert "timeout" in result.stderr.lower() or "timed out" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_execute_returns_output(self):
        sandbox = ProcessSandbox()
        code = """
import json
result = {"rows": 100, "columns": 5}
print(json.dumps(result))
"""
        result = await sandbox.execute(code)

        assert result.success
        assert '"rows": 100' in result.stdout

    @pytest.mark.asyncio
    async def test_execute_with_syntax_error(self):
        sandbox = ProcessSandbox()
        result = await sandbox.execute("def foo(:")

        assert not result.success
        assert "SyntaxError" in result.stderr or "syntax" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_sandbox_result_fields(self):
        result = SandboxResult(
            success=True,
            stdout="output",
            stderr="",
            return_code=0,
        )
        assert result.success
        assert result.return_code == 0
