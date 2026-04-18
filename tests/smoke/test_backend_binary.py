"""Backend binary smoke tests — packaging regression coverage.

Verifies the PyInstaller-built ``ds-agent-api`` binary can boot, expose its
HTTP surface, and avoid the import errors that source-tests cannot detect.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

from tests.smoke.conftest import RunningBackend

REQUEST_TIMEOUT = 10
pytestmark = pytest.mark.smoke


def _get(url: str) -> tuple[int, dict | str]:
    """Issue a GET. Returns (status_code, parsed-json-or-raw-text)."""
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except URLError as e:
        pytest.fail(f"Connection failed for {url}: {e}")


class TestHealthSurface:
    def test_health_endpoint_returns_ok(self, running_backend: RunningBackend):
        status, body = _get(f"{running_backend.base_url}/health")
        assert status == 200
        assert isinstance(body, dict)
        assert body.get("status") == "ok"

    def test_status_endpoint_responds(self, running_backend: RunningBackend):
        status, body = _get(f"{running_backend.base_url}/api/status")
        assert status == 200
        assert isinstance(body, dict)
        # Schema contract: required keys must be present even if empty.
        for key in ("model", "mode", "activeSessions"):
            assert key in body, f"/api/status missing key {key!r}: {body!r}"

    def test_config_endpoint_responds(self, running_backend: RunningBackend):
        status, body = _get(f"{running_backend.base_url}/api/config")
        # Auth-gated endpoints may return 401; we only assert it's reachable.
        assert status in (200, 401, 403), (
            f"unexpected status {status} from /api/config: {body!r}"
        )


class TestPackagingHealth:
    def test_no_module_import_errors_in_stderr(self, running_backend: RunningBackend):
        """Catch missing PyInstaller hidden imports and bad data paths."""
        # Drainer thread populates stderr_buffer; tolerate empty until first GC pass.
        stderr_blob = "".join(running_backend.stderr_buffer)
        for needle in ("ImportError", "ModuleNotFoundError", "DLL load failed"):
            assert needle not in stderr_blob, (
                f"packaging error detected in backend stderr ({needle!r}):\n"
                f"{stderr_blob[-1500:]}"
            )

    def test_process_still_alive_after_calls(self, running_backend: RunningBackend):
        """Sanity: backend must survive the smoke calls above this test."""
        assert running_backend.process.poll() is None, (
            "backend exited mid-suite — see stderr buffer for details"
        )
