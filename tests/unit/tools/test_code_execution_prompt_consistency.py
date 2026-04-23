import importlib
import re
from pathlib import Path


def test_code_execution_prompt_consistency():
    """Verify that all libraries listed as 'Available' in code_execution.py are actually importable."""
    prompt_file = Path("src/ds_agent/tools/code_execution.py")
    if not prompt_file.exists():
        return

    content = prompt_file.read_text(encoding="utf-8")
    # Search for "Available: pandas, numpy, ..."
    match = re.search(r"Available:\s*([a-zA-Z0-9, ]+)", content)
    if not match:
        return # Skip if no list found

    libs = [lib.strip() for lib in match.group(1).split(",")]
    for lib in libs:
        if not lib or lib.lower() == "etc":
            continue
        try:
            importlib.import_module(lib)
        except ImportError:
            import pytest
            pytest.fail(f"Library '{lib}' listed in code_execution.py is NOT available in the environment.")
