"""Policy-approved network sandbox with audit logging."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ds_agent.tools.code_security import CodeSecurityChecker
from ds_agent.tools.sandbox import ProcessSandbox, SandboxResult

_DEFAULT_ALLOWED_MODULES = (
    "requests",
    "httpx",
)


def _top_level_modules(module_names: tuple[str, ...]) -> set[str]:
    return {name.split(".")[0] for name in module_names}


class NetworkRunnerSandbox(ProcessSandbox):
    """Sandbox that allows audited network access only after approval."""

    def __init__(
        self,
        *,
        timeout: int = 120,
        working_dir: str | None = None,
        allowed_modules: tuple[str, ...] = _DEFAULT_ALLOWED_MODULES,
        approval_store: object | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "cli",
        emit_event: Callable[[str, dict[str, Any]], None] | None = None,
        approved: bool = False,
        audit_required: bool = True,
        allowed_domains: tuple[str, ...] = (),
    ) -> None:
        checker = CodeSecurityChecker(
            workspace_dir=Path(working_dir) if working_dir else None,
            allowed_external_modules=_top_level_modules(allowed_modules),
            allow_network=True,
        )
        super().__init__(
            timeout=timeout,
            working_dir=working_dir,
            security_checker=checker,
        )
        self.allowed_modules = allowed_modules
        self.audit_log: list[dict[str, Any]] = []
        self._approval_store = approval_store
        self._session_id = session_id
        self._run_id = run_id
        self._surface = surface
        self._emit_event = emit_event
        self._approved = approved
        self._audit_required = audit_required
        self._allowed_domains = allowed_domains

    async def execute(self, code: str, timeout: int | None = None) -> SandboxResult:
        approval_id: str | None = None
        if not self._approved:
            approval_id = self._request_approval()
            self._record_audit(
                status="approval_required",
                approval_id=approval_id,
            )
            return SandboxResult(
                success=False,
                stdout="",
                stderr=(
                    "Network access requires approval before execution."
                    + (f" approval_id={approval_id}" if approval_id else "")
                ),
                return_code=-3,
            )

        guarded_code = code
        if self._allowed_domains:
            guarded_code = self._wrap_with_domain_allowlist(code)

        result = await super().execute(guarded_code, timeout)
        self._record_audit(
            status="executed" if result.success else "failed",
            return_code=result.return_code,
            stderr=result.stderr[:500] if result.stderr else "",
        )
        return result

    def _request_approval(self) -> str | None:
        if self._approval_store is None or not self._session_id:
            return None
        approval = self._approval_store.create(  # type: ignore[attr-defined]
            session_id=self._session_id,
            run_id=self._run_id,
            surface=self._surface,
            question=(
                "Allow policy-approved network access for this tool execution?"
            ),
            options=["approve", "reject"],
            default="reject",
        )
        approval_id = getattr(approval, "approval_id", None)
        if callable(self._emit_event):
            self._emit_event(
                "approval.requested",
                {
                    "approvalId": approval_id,
                    "sessionId": self._session_id,
                    "runId": self._run_id,
                    "surface": self._surface,
                    "question": "Allow policy-approved network access for this tool execution?",
                },
            )
        return approval_id if isinstance(approval_id, str) else None

    def _record_audit(self, *, status: str, **metadata: Any) -> None:
        if not self._audit_required:
            return
        entry = {
            "status": status,
            "session_id": self._session_id,
            "run_id": self._run_id,
            "surface": self._surface,
            "allowed_domains": list(self._allowed_domains),
            **metadata,
        }
        self.audit_log.append(entry)
        if callable(self._emit_event):
            self._emit_event("sandbox.audit", entry)

    def _wrap_with_domain_allowlist(self, code: str) -> str:
        allowlist_json = json.dumps(sorted({domain.lower() for domain in self._allowed_domains}))
        return (
            "from urllib.parse import urlparse as _ds_agent_urlparse\n"
            f"_DS_AGENT_ALLOWED_DOMAINS = set({allowlist_json})\n"
            "\n"
            "def _ds_agent_assert_allowed(url):\n"
            "    host = (_ds_agent_urlparse(str(url)).hostname or '').lower()\n"
            "    if not host:\n"
            "        return\n"
            "    if host in _DS_AGENT_ALLOWED_DOMAINS:\n"
            "        return\n"
            "    if any(host.endswith('.' + allowed) for allowed in _DS_AGENT_ALLOWED_DOMAINS):\n"
            "        return\n"
            "    raise PermissionError(\n"
            "        f\"Network access to '{host}' is not allowed by the active skill policy.\"\n"
            "    )\n"
            "\n"
            "try:\n"
            "    import requests as _ds_agent_requests\n"
            "    _ds_agent_requests_session_request = _ds_agent_requests.sessions.Session.request\n"
            "\n"
            "    def _ds_agent_requests_guard(self, method, url, *args, **kwargs):\n"
            "        _ds_agent_assert_allowed(url)\n"
            "        return _ds_agent_requests_session_request(self, method, url, *args, **kwargs)\n"
            "\n"
            "    _ds_agent_requests.sessions.Session.request = _ds_agent_requests_guard\n"
            "except Exception:\n"
            "    pass\n"
            "\n"
            "try:\n"
            "    import httpx as _ds_agent_httpx\n"
            "    _ds_agent_httpx_client_request = _ds_agent_httpx.Client.request\n"
            "    _ds_agent_httpx_async_request = _ds_agent_httpx.AsyncClient.request\n"
            "\n"
            "    def _ds_agent_httpx_guard(self, method, url, *args, **kwargs):\n"
            "        _ds_agent_assert_allowed(url)\n"
            "        return _ds_agent_httpx_client_request(self, method, url, *args, **kwargs)\n"
            "\n"
            "    async def _ds_agent_httpx_async_guard(self, method, url, *args, **kwargs):\n"
            "        _ds_agent_assert_allowed(url)\n"
            "        return await _ds_agent_httpx_async_request(self, method, url, *args, **kwargs)\n"
            "\n"
            "    _ds_agent_httpx.Client.request = _ds_agent_httpx_guard\n"
            "    _ds_agent_httpx.AsyncClient.request = _ds_agent_httpx_async_guard\n"
            "except Exception:\n"
            "    pass\n"
            "\n"
            + code
        )
