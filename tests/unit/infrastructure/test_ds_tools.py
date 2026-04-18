"""Parametrized tests for all DS tool wrappers (Phase 5).

All DS tools share an identical pattern: build preamble/code → sandbox.execute → return.
We patch create_secure_sandbox at the shared runner level.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ds_agent.tools.sandbox import SandboxResult

# Each tuple: (module_path, function_name, kwargs, has_preamble)
# has_preamble: True = tool uses preamble + user code; False = tool generates code internally
TOOLS = [
    (
        "ds_agent.tools.eda",
        "run_eda",
        {"code": "print(1)", "data_path": "/d.csv"},
        True,
    ),
    (
        "ds_agent.tools.modeling",
        "train_model",
        {"code": "print(1)", "data_path": "/d.csv", "target_column": "y"},
        True,
    ),
    (
        "ds_agent.tools.evaluation",
        "evaluate_model",
        {
            "code": "print(1)",
            "model_path": "/m.pkl",
            "test_data_path": "/d.csv",
            "target_column": "y",
        },
        True,
    ),
    (
        "ds_agent.tools.feature_eng",
        "feature_engineer",
        {"code": "print(1)", "input_path": "/d.csv", "output_path": "/o.csv"},
        True,
    ),
    (
        "ds_agent.tools.reporting",
        "generate_report",
        {"code": "print(1)", "project_dir": "/proj", "output_path": "/r.md"},
        True,
    ),
    (
        "ds_agent.tools.deployment",
        "generate_deployment",
        {"code": "print(1)", "model_path": "/m.pkl", "output_dir": "/deploy"},
        True,
    ),
    (
        "ds_agent.tools.data_loader",
        "data_loader",
        {"file_path": "/d.csv"},
        False,
    ),
    (
        "ds_agent.tools.data_profiler",
        "data_profiler",
        {"file_path": "/d.csv"},
        False,
    ),
]


def _tool_ids():
    return [t[1] for t in TOOLS]


class TestDSToolSuccess:
    """All DS tools return stdout on success."""

    @pytest.mark.parametrize("module,func_name,kwargs,_", TOOLS, ids=_tool_ids())
    @pytest.mark.asyncio
    async def test_success_returns_stdout(self, module, func_name, kwargs, _):
        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(
            return_value=SandboxResult(success=True, stdout="tool output", stderr="", return_code=0)
        )

        _path = "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox"
        with patch(_path, return_value=mock_sandbox):
            import importlib

            mod = importlib.import_module(module)
            func = getattr(mod, func_name)
            result = await func(**kwargs)

        assert "tool output" in result or "completed" in result.lower()


class TestDSToolError:
    """All DS tools return error message on failure."""

    @pytest.mark.parametrize("module,func_name,kwargs,_", TOOLS, ids=_tool_ids())
    @pytest.mark.asyncio
    async def test_error_returns_stderr(self, module, func_name, kwargs, _):
        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(
            return_value=SandboxResult(
                success=False,
                stdout="",
                stderr="NameError: name 'x' is not defined",
                return_code=1,
            )
        )

        _path = "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox"
        with patch(_path, return_value=mock_sandbox):
            import importlib

            mod = importlib.import_module(module)
            func = getattr(mod, func_name)
            result = await func(**kwargs)

        assert "error" in result.lower() or "Error" in result


class TestDSToolSandboxCreation:
    """Verify sandbox is created with expected timeout."""

    @pytest.mark.parametrize("module,func_name,kwargs,_", TOOLS, ids=_tool_ids())
    @pytest.mark.asyncio
    async def test_sandbox_created(self, module, func_name, kwargs, _):
        mock_sandbox = MagicMock()
        mock_sandbox.execute = AsyncMock(
            return_value=SandboxResult(success=True, stdout="ok", stderr="", return_code=0)
        )

        _path = "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox"
        with patch(_path, return_value=mock_sandbox) as mock_create:
            import importlib

            mod = importlib.import_module(module)
            func = getattr(mod, func_name)
            await func(**kwargs)

        mock_create.assert_called_once()
        # Verify timeout is a positive integer
        call_kwargs = mock_create.call_args
        timeout = call_kwargs.kwargs.get("timeout")
        if timeout is None and call_kwargs.args:
            timeout = call_kwargs.args[0]
        if timeout is not None:
            assert isinstance(timeout, int)
            assert timeout > 0


class TestDSToolPreambleContent:
    """Audit 6.2: validate that DS tools inject correct variable names into preamble code.

    The existing tests only check that sandbox *was called*, not *what code was passed*.
    These tests inspect the actual code string sent to the sandbox to prevent silent
    regressions like wrong variable names or missing path injection.
    """

    def _capture_code(self, mock_sandbox: MagicMock) -> str:
        """Extract the code string passed to sandbox.execute()."""
        return mock_sandbox.execute.call_args[0][0]

    def _make_sandbox(self, stdout: str = "ok") -> MagicMock:
        m = MagicMock()
        m.execute = AsyncMock(
            return_value=SandboxResult(success=True, stdout=stdout, stderr="", return_code=0)
        )
        return m

    @pytest.mark.asyncio
    async def test_eda_injects_data_path_and_output_dir(self):
        """run_eda must inject DATA_PATH and OUTPUT_DIR into preamble."""
        mock_sandbox = self._make_sandbox()
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=mock_sandbox
        ):
            from ds_agent.tools.eda import run_eda

            await run_eda(code="print(DATA_PATH)", data_path="/data/iris.csv", output_dir="/out")

        code = self._capture_code(mock_sandbox)
        assert "DATA_PATH = '/data/iris.csv'" in code
        assert "OUTPUT_DIR = '/out'" in code
        # user code is appended after preamble
        assert "print(DATA_PATH)" in code

    @pytest.mark.asyncio
    async def test_eda_output_dir_none_by_default(self):
        """run_eda with no output_dir must set OUTPUT_DIR = None."""
        mock_sandbox = self._make_sandbox()
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=mock_sandbox
        ):
            from ds_agent.tools.eda import run_eda

            await run_eda(code="x=1", data_path="/data/iris.csv")

        code = self._capture_code(mock_sandbox)
        assert "OUTPUT_DIR = None" in code

    @pytest.mark.asyncio
    async def test_modeling_injects_required_variables(self):
        """train_model must inject DATA_PATH, TARGET_COLUMN, and MODEL_OUTPUT_PATH."""
        mock_sandbox = self._make_sandbox()
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=mock_sandbox
        ):
            from ds_agent.tools.modeling import train_model

            await train_model(
                code="print(DATA_PATH)",
                data_path="/data/train.csv",
                target_column="survived",
                model_output_path="/models/rf.pkl",
            )

        code = self._capture_code(mock_sandbox)
        assert "DATA_PATH = '/data/train.csv'" in code
        assert "TARGET_COLUMN = 'survived'" in code
        assert "MODEL_OUTPUT_PATH = '/models/rf.pkl'" in code

    @pytest.mark.asyncio
    async def test_data_loader_embeds_file_path(self):
        """data_loader must embed file_path as a Python literal in generated code."""
        mock_sandbox = self._make_sandbox(stdout=json.dumps({"shape": [100, 5], "columns": ["a"]}))
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=mock_sandbox
        ):
            from ds_agent.tools.data_loader import data_loader

            await data_loader(file_path="/data/train.csv")

        code = self._capture_code(mock_sandbox)
        # file_path must be inserted as a Python repr string literal
        assert "file_path = '/data/train.csv'" in code
        # sample_rows default (5) must also be injected
        assert "sample_rows = 5" in code

    @pytest.mark.asyncio
    async def test_feature_engineer_injects_paths(self):
        """feature_engineer must inject INPUT_PATH and OUTPUT_PATH."""
        mock_sandbox = self._make_sandbox()
        with patch(
            "ds_agent.tools._ds_sandbox_runner.create_secure_sandbox", return_value=mock_sandbox
        ):
            from ds_agent.tools.feature_eng import feature_engineer

            await feature_engineer(
                code="x=1", input_path="/data/raw.csv", output_path="/data/features.csv"
            )

        code = self._capture_code(mock_sandbox)
        assert "INPUT_PATH = '/data/raw.csv'" in code
        assert "OUTPUT_PATH = '/data/features.csv'" in code
