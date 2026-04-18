"""Static import-boundary checks for Clean Architecture contracts.

This is a lightweight repo-local guard for CI and local verification. The same
domain contract is also expressed in `.importlinter` for teams that want to run
the external Import Linter tool directly.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


@dataclass(frozen=True, slots=True)
class ImportContract:
    """One forbidden-import contract."""

    name: str
    source_modules: tuple[str, ...]
    forbidden_modules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportViolation:
    """One source file importing a forbidden module."""

    contract_name: str
    file_path: Path
    line_number: int
    importer_module: str
    imported_module: str


CONTRACTS: tuple[ImportContract, ...] = (
    ImportContract(
        name="domain_independence",
        source_modules=("ds_agent.domain",),
        forbidden_modules=(
            "ds_agent.api",
            "ds_agent.application",
            "ds_agent.channels",
            "ds_agent.cli",
            "ds_agent.config",
            "ds_agent.evaluation",
            "ds_agent.gateway",
            "ds_agent.infrastructure",
            "ds_agent.memory",
            "ds_agent.providers",
            "ds_agent.runtime",
            "ds_agent.self_improve",
            "ds_agent.tools",
        ),
    ),
    ImportContract(
        name="application_no_infrastructure",
        source_modules=("ds_agent.application",),
        forbidden_modules=("ds_agent.infrastructure",),
    ),
)


def module_name_for_path(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def iter_python_files(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.rglob("*.py") if path.is_file())


def imported_modules(node: ast.AST) -> list[tuple[str, int]]:
    if isinstance(node, ast.Import):
        return [(alias.name, node.lineno) for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level > 0 or node.module is None:
            return []
        return [(node.module, node.lineno)]
    return []


def find_contract_violations() -> list[ImportViolation]:
    violations: list[ImportViolation] = []
    for contract in CONTRACTS:
        for source_module in contract.source_modules:
            source_dir = SRC_ROOT / Path(*source_module.split("."))
            for file_path in iter_python_files(source_dir):
                importer_module = module_name_for_path(file_path)
                tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
                for node in ast.walk(tree):
                    for imported_module, line_number in imported_modules(node):
                        if any(
                            imported_module == forbidden
                            or imported_module.startswith(f"{forbidden}.")
                            for forbidden in contract.forbidden_modules
                        ):
                            violations.append(
                                ImportViolation(
                                    contract_name=contract.name,
                                    file_path=file_path,
                                    line_number=line_number,
                                    importer_module=importer_module,
                                    imported_module=imported_module,
                                )
                            )
    return violations


def main() -> int:
    violations = find_contract_violations()
    if not violations:
        print("import contracts: ok")
        return 0

    print("import contracts: violations found")
    for violation in violations:
        relative_path = violation.file_path.relative_to(REPO_ROOT)
        print(
            f"- [{violation.contract_name}] "
            f"{relative_path}:{violation.line_number} "
            f"{violation.importer_module} -> {violation.imported_module}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
