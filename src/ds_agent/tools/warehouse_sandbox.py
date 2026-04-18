"""Read-only warehouse sandbox with DB-oriented import allowlist."""

from __future__ import annotations

from pathlib import Path

from ds_agent.tools.code_security import CodeSecurityChecker
from ds_agent.tools.sandbox import ProcessSandbox

_DEFAULT_ALLOWED_MODULES = (
    "snowflake.connector",
    "google.cloud.bigquery",
    "psycopg2",
    "pandas",
    "numpy",
)


def _top_level_modules(module_names: tuple[str, ...]) -> set[str]:
    return {name.split(".")[0] for name in module_names}


class WarehouseRunnerSandbox(ProcessSandbox):
    """Sandbox that only permits stdlib plus warehouse-related libraries."""

    def __init__(
        self,
        *,
        timeout: int = 120,
        working_dir: str | None = None,
        allowed_modules: tuple[str, ...] = _DEFAULT_ALLOWED_MODULES,
    ) -> None:
        checker = CodeSecurityChecker(
            workspace_dir=Path(working_dir) if working_dir else None,
            allowed_external_modules=_top_level_modules(allowed_modules),
        )
        super().__init__(
            timeout=timeout,
            working_dir=working_dir,
            security_checker=checker,
        )
        self.allowed_modules = allowed_modules
