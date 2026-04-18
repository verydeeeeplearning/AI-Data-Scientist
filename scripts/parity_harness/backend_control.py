"""Subprocess lifecycle helper for the packaged ``ds-agent-api.exe`` binary.

Phase 3 harness uses the PyInstaller-bundled backend to achieve true
process-level isolation. All scientific deps (numpy, pandas, scipy,
sklearn) live inside the bundle — the host venv does not need them.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_READY_RE = re.compile(r"READY:(\d+):([0-9a-fA-F]+)")


@dataclass
class BackendHandle:
    """Running backend instance."""

    process: subprocess.Popen[str]
    port: int
    token: str
    pid: int
    log_path: Path

    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/health"

    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws?token={self.token}"


class BackendManager:
    """Spawn and tear down the packaged backend binary."""

    def __init__(
        self,
        *,
        binary_path: Path,
        port_base: int = 18890,
        ready_timeout_s: float = 30.0,
        kill_timeout_s: float = 5.0,
        log_dir: Path,
    ) -> None:
        self._binary = binary_path
        self._port_base = port_base
        self._ready_timeout = ready_timeout_s
        self._kill_timeout = kill_timeout_s
        self._log_dir = log_dir
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def spawn(self, *, port_offset: int = 0, label: str = "backend") -> BackendHandle:
        port = self._port_base + port_offset
        log_path = self._log_dir / f"{label}-{port}.log"
        log_handle = open(log_path, "w", encoding="utf-8")
        env = os.environ.copy()
        # Phase 3 constraint: no real external calls. Mocked provider path
        # = no API key → _NoApiKeyProvider canned response.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("OPENAI_API_KEY", None)
        env.pop("GOOGLE_API_KEY", None)
        env.pop("DS_AGENT_LIVE_SMOKE", None)
        env["DS_AGENT_SENTRY_DSN"] = ""  # P0-07: disable Sentry in tests

        proc = subprocess.Popen(
            [str(self._binary), "--host", "127.0.0.1", "--port", str(port)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
        )

        # Poll log for READY emit
        deadline = time.monotonic() + self._ready_timeout
        resolved_port: int | None = None
        token: str = ""
        while time.monotonic() < deadline:
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                text = ""
            m = _READY_RE.search(text)
            if m:
                resolved_port = int(m.group(1))
                token = m.group(2)
                break
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Backend exited before READY (code={proc.returncode}). Log: {log_path}"
                )
            time.sleep(0.25)

        if resolved_port is None:
            # Kill the orphan before raising
            self._kill(proc)
            log_handle.close()
            raise TimeoutError(
                f"Backend did not emit READY within {self._ready_timeout}s. Log: {log_path}"
            )

        return BackendHandle(
            process=proc,
            port=resolved_port,
            token=token,
            pid=proc.pid,
            log_path=log_path,
        )

    def stop(self, handle: BackendHandle) -> dict:
        """Terminate the spawned backend. Returns cleanup confirmation."""
        if handle.process.poll() is not None:
            return {
                "pid": handle.pid,
                "exit_code": handle.process.returncode,
                "killed": False,
                "already_exited": True,
            }
        self._kill(handle.process)
        try:
            handle.process.wait(timeout=self._kill_timeout)
        except subprocess.TimeoutExpired:
            # Force
            self._kill(handle.process, force=True)
            try:
                handle.process.wait(timeout=self._kill_timeout)
            except subprocess.TimeoutExpired:
                pass
        return {
            "pid": handle.pid,
            "exit_code": handle.process.returncode,
            "killed": True,
            "already_exited": False,
        }

    @staticmethod
    def _kill(proc: subprocess.Popen, *, force: bool = False) -> None:
        if sys.platform == "win32":
            # Use taskkill for reliable termination on Windows.
            flag = "/F" if force else ""
            try:
                subprocess.run(
                    ["taskkill"] + ([flag] if flag else []) + ["/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    check=False,
                )
            except FileNotFoundError:
                try:
                    proc.terminate()
                except Exception:
                    pass
        else:
            try:
                proc.send_signal(signal.SIGKILL if force else signal.SIGTERM)
            except Exception:
                pass
