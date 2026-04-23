"""Architecture test: application layer must not import infrastructure.

This test enforces the Clean Architecture Dependency Rule at the
``ds_agent.application`` boundary. The application layer may only
depend on abstractions (ports) it declares itself and on the domain
layer; concrete adapters live in ``ds_agent.infrastructure`` and are
wired at the composition root.

Extends A01 scope from ``semantic_application_no_infra`` (which covers
only ``ds_agent.memory.semantic``) to the entire ``ds_agent.application``
package.

Carve-out: application → ds_agent.runtime is PERMITTED (not tested here).
  Reason: RuntimeEventRecord is used in trust-metadata ports and use cases
          as a bounded, documented exception.  See scripts/check_import_contracts.py
          for the canonical carve-out declaration.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
APPLICATION_ROOT = REPO_ROOT / "src" / "ds_agent" / "application"
FORBIDDEN_PREFIX = "ds_agent.infrastructure"


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _find_forbidden_imports(root: Path, forbidden_prefix: str) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for file_path in _iter_python_files(root):
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 0 or node.module is None:
                    continue
                module = node.module
                if module == forbidden_prefix or module.startswith(f"{forbidden_prefix}."):
                    violations.append((file_path, node.lineno, module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module == forbidden_prefix or module.startswith(f"{forbidden_prefix}."):
                        violations.append((file_path, node.lineno, module))
    return violations


def test_application_layer_has_no_infrastructure_imports() -> None:
    """``ds_agent.application`` must contain zero static imports of ``ds_agent.infrastructure``."""
    violations = _find_forbidden_imports(APPLICATION_ROOT, FORBIDDEN_PREFIX)
    rendered = "\n".join(
        f"  {path.relative_to(REPO_ROOT)}:{line} -> {module}" for path, line, module in violations
    )
    assert not violations, (
        "application layer has forbidden infrastructure imports:\n" + rendered
    )


@pytest.mark.parametrize(
    "target",
    [
        "lineage_capture_service.py",
        "reproducibility_exporter.py",
        "scheduler_service.py",
    ],
)
def test_previously_flagged_services_are_clean(target: str) -> None:
    """Regression guard for the three A01-reported violations."""
    file_path = APPLICATION_ROOT / "services" / target
    assert file_path.exists(), f"expected application service missing: {file_path}"
    violations = _find_forbidden_imports(file_path.parent, FORBIDDEN_PREFIX)
    offending = [v for v in violations if v[0] == file_path]
    rendered = "\n".join(f"  line {line} -> {module}" for _, line, module in offending)
    assert not offending, (
        f"{target} still imports ds_agent.infrastructure:\n" + rendered
    )
