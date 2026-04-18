"""Semantic memory layer-dependency guard.

Verifies Clean Architecture dependency rules for the semantic memory module:
  - domain/ must not import from application/ or infrastructure/
  - application/ must not import from infrastructure/

Reuses the AST-parsing pattern from check_import_contracts.py.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
SEMANTIC_ROOT = SRC_ROOT / "ds_agent" / "memory" / "semantic"


@dataclass(frozen=True, slots=True)
class LayerViolation:
    """One source file importing a forbidden layer."""

    rule_name: str
    file_path: Path
    line_number: int
    imported_module: str


LAYER_RULES: list[tuple[str, Path, tuple[str, ...]]] = [
    (
        "semantic_domain_independence",
        SEMANTIC_ROOT / "domain",
        (
            "ds_agent.memory.semantic.application",
            "ds_agent.memory.semantic.infrastructure",
            "ds_agent.infrastructure",
            "ds_agent.application",
            "ds_agent.api",
            "ds_agent.cli",
            "ds_agent.gateway",
            "ds_agent.runtime",
            "ds_agent.tools",
        ),
    ),
    (
        "semantic_application_no_infra",
        SEMANTIC_ROOT / "application",
        (
            "ds_agent.memory.semantic.infrastructure",
            "ds_agent.infrastructure",
            "ds_agent.api",
            "ds_agent.cli",
            "ds_agent.gateway",
            "ds_agent.runtime",
        ),
    ),
]


def _iter_python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*.py") if p.is_file())


def _imported_modules(node: ast.AST) -> list[tuple[str, int]]:
    if isinstance(node, ast.Import):
        return [(alias.name, node.lineno) for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level > 0 or node.module is None:
            return []
        return [(node.module, node.lineno)]
    return []


def find_violations() -> list[LayerViolation]:
    violations: list[LayerViolation] = []
    for rule_name, source_dir, forbidden in LAYER_RULES:
        for file_path in _iter_python_files(source_dir):
            tree = ast.parse(
                file_path.read_text(encoding="utf-8"),
                filename=str(file_path),
            )
            for node in ast.walk(tree):
                for imported_module, line_number in _imported_modules(node):
                    if any(
                        imported_module == f
                        or imported_module.startswith(f"{f}.")
                        for f in forbidden
                    ):
                        violations.append(
                            LayerViolation(
                                rule_name=rule_name,
                                file_path=file_path,
                                line_number=line_number,
                                imported_module=imported_module,
                            ),
                        )
    return violations


def main() -> int:
    violations = find_violations()
    if not violations:
        print("semantic layer deps: ok")
        return 0

    print("semantic layer deps: violations found")
    for v in violations:
        relative = v.file_path.relative_to(REPO_ROOT)
        print(
            f"- [{v.rule_name}] {relative}:{v.line_number} "
            f"-> {v.imported_module}",
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
