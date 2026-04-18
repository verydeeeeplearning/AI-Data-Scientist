import sys
import pytest
from unittest.mock import patch
from ds_agent.tools.sandbox import _build_exec_command

def test_build_exec_command_not_frozen():
    """Verify that in source mode, it uses sys.executable directly."""
    with patch.object(sys, "frozen", False, create=True):
        cmd = _build_exec_command("script.py")
        assert cmd == [sys.executable, "script.py"]

def test_build_exec_command_frozen():
    """Verify that in frozen mode, it uses --mode exec subcommand."""
    with patch.object(sys, "frozen", True, create=True):
        cmd = _build_exec_command("script.py")
        assert cmd == [sys.executable, "--mode", "exec", "script.py"]

def test_build_exec_command_missing_frozen():
    """Verify that when sys.frozen is missing, it defaults to source mode."""
    if hasattr(sys, "frozen"):
        delattr(sys, "frozen")
    
    cmd = _build_exec_command("script.py")
    assert cmd == [sys.executable, "script.py"]
