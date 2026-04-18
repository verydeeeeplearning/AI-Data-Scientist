"""CI-integrated test for semantic memory layer dependency rules.

Delegates to scripts/check_layer_deps.py to ensure domain/ and application/
layers inside ds_agent.memory.semantic have zero forbidden imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the scripts directory is importable.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_layer_deps import find_violations  # noqa: E402


def test_semantic_domain_has_no_forbidden_imports() -> None:
    violations = [
        v for v in find_violations()
        if v.rule_name == "semantic_domain_independence"
    ]
    assert violations == [], (
        "semantic domain layer has forbidden imports:\n"
        + "\n".join(
            f"  {v.file_path.relative_to(REPO_ROOT)}:{v.line_number} -> {v.imported_module}"
            for v in violations
        )
    )


def test_semantic_application_has_no_infrastructure_imports() -> None:
    violations = [
        v for v in find_violations()
        if v.rule_name == "semantic_application_no_infra"
    ]
    assert violations == [], (
        "semantic application layer has infrastructure imports:\n"
        + "\n".join(
            f"  {v.file_path.relative_to(REPO_ROOT)}:{v.line_number} -> {v.imported_module}"
            for v in violations
        )
    )
