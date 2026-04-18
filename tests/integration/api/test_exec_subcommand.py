import subprocess
import sys
import tempfile
from pathlib import Path

def test_app_exec_mode_success():
    """Verify that 'python -m ds_agent.api.app --mode exec SCRIPT' runs the script."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("import sys\nprint('HELLO_FROM_EXEC_MODE')\nsys.exit(0)")
        script_path = f.name
    
    try:
        # Run using current python interpreter to avoid dependency issues in the test environment
        result = subprocess.run(
            [sys.executable, "-m", "ds_agent.api.app", "--mode", "exec", script_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert "HELLO_FROM_EXEC_MODE" in result.stdout
    finally:
        Path(script_path).unlink(missing_ok=True)

def test_app_exec_mode_failure():
    """Verify that script failures propagate exit codes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("import sys\nsys.exit(42)")
        script_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ds_agent.api.app", "--mode", "exec", script_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 42
    finally:
        Path(script_path).unlink(missing_ok=True)

def test_app_exec_mode_no_script():
    """Verify that --mode exec without a script path returns error."""
    result = subprocess.run(
        [sys.executable, "-m", "ds_agent.api.app", "--mode", "exec"],
        capture_output=True,
        text=True,
        timeout=10
    )
    assert result.returncode == 2
    assert "requires a SCRIPT path argument" in result.stderr
