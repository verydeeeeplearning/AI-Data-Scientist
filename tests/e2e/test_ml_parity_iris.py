
import pytest


@pytest.mark.asyncio
async def test_ml_parity_iris_source():
    """End-to-end smoke test: LLM generates sklearn code -> sandbox execute success."""
    # This test simulates a run in 'source' mode (non-frozen)

    # We'll verify that the tools are available and the sandbox can run sklearn.

    code = (
        "import sklearn\n"
        "from sklearn.datasets import load_iris\n"
        "from sklearn.linear_model import LogisticRegression\n"
        "import pandas as pd\n"
        "data = load_iris()\n"
        "df = pd.DataFrame(data.data, columns=data.feature_names)\n"
        "model = LogisticRegression(max_iter=200)\n"
        "model.fit(df, data.target)\n"
        "print(f'SCORE: {model.score(df, data.target):.4f}')"
    )

    from ds_agent.tools.sandbox import create_sandbox
    sandbox = create_sandbox()
    result = await sandbox.execute(code)

    assert result.success, f"Execution failed: {result.stderr}"
    assert "SCORE:" in result.stdout
    score = float(result.stdout.split("SCORE:")[1].strip())
    assert score > 0.9

@pytest.mark.asyncio
async def test_ml_parity_iris_packaged_mock():
    """Verify that sandbox correctly branches to --mode exec in mock frozen mode."""
    import sys
    from unittest.mock import patch

    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", "ds-agent-api.exe"):
        from ds_agent.tools.sandbox import _build_exec_command
        cmd = _build_exec_command("probe.py")
        assert cmd == ["ds-agent-api.exe", "--mode", "exec", "probe.py"]
