"""Shared smoke-test fixtures: locate the packaged binary and run it."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINARY = REPO_ROOT / "dist" / "ds-agent-backend" / (
    "ds-agent-api.exe" if sys.platform == "win32" else "ds-agent-api"
)

READY_TIMEOUT_SECONDS = 30


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _resolve_binary() -> Path | None:
    """Return the configured binary path or None if unavailable.

    Honours ``PACKAGED_BINARY_PATH`` env var first; falls back to the default
    ``dist/ds-agent-backend/ds-agent-api(.exe)`` location used by
    ``scripts/build_backend.py``.
    """
    override = os.environ.get("PACKAGED_BINARY_PATH")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.exists() else None
    return DEFAULT_BINARY if DEFAULT_BINARY.exists() else None


@dataclass
class RunningBackend:
    """Handle returned by the ``running_backend`` fixture."""

    base_url: str
    port: int
    process: subprocess.Popen
    stderr_buffer: list[str]


def _drain_stderr(process: subprocess.Popen, sink: list[str]) -> None:
    """Background reader so the child never blocks on a full stderr pipe."""
    stream = process.stderr
    if stream is None:
        return
    for raw_line in iter(stream.readline, b""):
        try:
            sink.append(raw_line.decode("utf-8", errors="replace"))
        except Exception:
            sink.append(repr(raw_line))


@pytest.fixture(scope="module")
def packaged_binary() -> Path:
    binary = _resolve_binary()
    if binary is None:
        pytest.skip(
            "Packaged binary not found. Set PACKAGED_BINARY_PATH or run "
            "`python scripts/build_backend.py` first."
        )
    return binary


@pytest.fixture(scope="module")
def running_backend(packaged_binary: Path) -> Iterator[RunningBackend]:
    """Spawn the packaged backend and wait for its READY signal."""
    port = _find_free_port()
    env = {**os.environ, "DS_AGENT_WS_TOKEN": "smoke-token"}
    process = subprocess.Popen(
        [str(packaged_binary), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(packaged_binary.parent),
    )

    stderr_buffer: list[str] = []
    drainer = threading.Thread(
        target=_drain_stderr,
        args=(process, stderr_buffer),
        daemon=True,
    )
    drainer.start()

    actual_port = port
    ready = False
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        line = process.stdout.readline() if process.stdout else b""
        if not line:
            time.sleep(0.1)
            continue
        decoded = line.decode("utf-8", errors="replace").strip()
        if decoded.startswith("READY:"):
            parts = decoded.split(":")
            if len(parts) >= 2 and parts[1].isdigit():
                actual_port = int(parts[1])
            ready = True
            break

    if not ready:
        process.kill()
        process.wait(timeout=5)
        stderr_text = "".join(stderr_buffer)[-2000:]
        pytest.fail(
            f"Backend did not emit READY within {READY_TIMEOUT_SECONDS}s. "
            f"stderr tail:\n{stderr_text}"
        )

    handle = RunningBackend(
        base_url=f"http://127.0.0.1:{actual_port}",
        port=actual_port,
        process=process,
        stderr_buffer=stderr_buffer,
    )
    try:
        yield handle
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "smoke: packaged-binary smoke test (skipped when binary is missing).",
    )
