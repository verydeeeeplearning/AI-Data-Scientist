"""FastAPI application — DS Agent backend for Electron desktop app.

Entry point::

    python -m ds_agent.api.app --port 18790

Prints ``READY:<port>:<token>`` to stdout so Electron's main process knows the
backend is ready to accept WebSocket connections. The token is a one-time
secret used to authenticate the WebSocket handshake (SEC-01).
"""

from __future__ import annotations

import os
import secrets
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

# Force stdout/stderr to UTF-8 so structlog (which writes via print()) can
# emit non-ASCII characters on Windows where the default console codepage is
# cp949 / cp1252. Without this, any log message containing em-dash, Korean,
# or other Unicode characters crashes the logger with UnicodeEncodeError
# (and since logging happens inside the sandbox wrapper, the whole tool
# call fails in 0.0s before the subprocess even starts).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except (AttributeError, OSError):
    pass

import structlog
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ds_agent.api.routes.access_log import router as access_log_router
from ds_agent.api.routes.admin import router as admin_router
from ds_agent.api.routes.approval_grants import router as approval_grants_router
from ds_agent.api.routes.cards import router as cards_router
from ds_agent.api.routes.certification import router as certification_router
from ds_agent.api.routes.config import router as config_router
from ds_agent.api.routes.export import router as export_router
from ds_agent.api.routes.files import router as files_router
from ds_agent.api.routes.integrations import router as integrations_router
from ds_agent.api.routes.mission import router as mission_router
from ds_agent.api.routes.onboarding import router as onboarding_router
from ds_agent.api.routes.status import router as status_router
from ds_agent.api.routes.support import router as support_router
from ds_agent.api.routes.task_contracts import router as task_contract_router
from ds_agent.api.routes.trust import router as trust_router
from ds_agent.api.routes.usage import router as usage_router
from ds_agent.api.routes.web_push import router as web_push_router
from ds_agent.api.routes.work_objects import router as work_object_router
from ds_agent.api.routes.workspace import router as workspace_router
from ds_agent.api.ws_handler import AppState, WsRpcHandler
from ds_agent.infrastructure.observability import (
    configure_backend_observability,
    shutdown_backend_observability,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle."""
    app.state.app_state = AppState()
    configure_backend_observability(app.state.app_state.config)
    from ds_agent.gateway.bot_supervisor import BotSupervisor

    telegram_supervisor = BotSupervisor(
        app.state.app_state.config,
        app_state=app.state.app_state,
    )
    app.state.app_state.set_telegram_supervisor(telegram_supervisor)
    telegram_config = app.state.app_state.config.channels.telegram
    if telegram_config.enabled and telegram_config.bot_token:
        await telegram_supervisor.start()
    await app.state.app_state.start_background_runtime()
    logger.info("api_started", port=app.state.port if hasattr(app.state, "port") else "?")
    # Emit READY only after startup work is done. Uvicorn binds the listening
    # socket BEFORE invoking lifespan.startup, so by this point /health and /ws
    # are guaranteed to accept connections. Emitting earlier (before
    # uvicorn.run) creates a race where Electron's health probe hits a closed
    # port and falsely reports the backend as failed.
    if getattr(app.state, "emit_ready", False):
        port = getattr(app.state, "port", "?")
        token = getattr(app.state, "ws_token", "") or ""
        print(f"READY:{port}:{token}", flush=True)
        sys.stdout.flush()
    yield
    await app.state.app_state.stop_telegram_gateway()
    await app.state.app_state.stop_background_runtime()
    shutdown_backend_observability()
    logger.info("api_stopped")


def create_app(ws_token: str | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    Args:
        ws_token: One-time secret for WebSocket authentication (SEC-01).
                  When provided, ``/ws`` rejects connections missing the token.
                  Pass ``None`` only in tests to disable auth.
    """
    app = FastAPI(
        title="DS Agent API",
        version="0.1.0",
        lifespan=lifespan,
    )
    # Store token in app state for validation
    app.state.ws_token = ws_token

    # SEC-04: Restricted CORS — only allow known origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:5173",
            "http://localhost:18790",  # Self
            "http://127.0.0.1:18790",
            "app://.",  # Electron production
        ],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # HTTP routes
    app.include_router(admin_router)
    app.include_router(approval_grants_router)
    app.include_router(cards_router)
    app.include_router(certification_router)
    app.include_router(status_router)
    app.include_router(config_router)
    app.include_router(access_log_router)
    app.include_router(export_router)
    app.include_router(files_router)
    app.include_router(support_router)
    app.include_router(task_contract_router)
    app.include_router(trust_router)
    app.include_router(usage_router)
    app.include_router(integrations_router)
    app.include_router(mission_router)
    app.include_router(onboarding_router)
    app.include_router(web_push_router)
    app.include_router(work_object_router)
    app.include_router(workspace_router)

    # Health check
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # WebSocket endpoint — SEC-01: token authentication
    @app.websocket("/ws")
    async def ws_endpoint(
        websocket: WebSocket,
        token: str | None = Query(default=None),
    ) -> None:
        # Validate token when auth is enabled
        # DEV-ONLY: DS_AGENT_DEV_NO_AUTH=1 bypasses token check (Playwright audit)
        expected = app.state.ws_token
        if (
            expected is not None
            and token != expected
            and os.getenv("DS_AGENT_DEV_NO_AUTH") != "1"
        ):
            logger.warning("ws_auth_rejected", reason="invalid_or_missing_token")
            await websocket.close(code=1008)  # Policy violation
            return

        await websocket.accept()
        handler = WsRpcHandler(state=app.state.app_state, websocket=websocket)
        app.state.app_state.register_runtime_listener(handler._callbacks.emit_event)
        logger.info("ws_connected")

        try:
            while True:
                data = await websocket.receive_json()
                await handler.handle_message(data)
        except WebSocketDisconnect:
            logger.info("ws_disconnected")
        except Exception as e:
            logger.error("ws_error", error=str(e))
        finally:
            app.state.app_state.unregister_runtime_listener(handler._callbacks.emit_event)
            # CON-05: Clean up background tasks on disconnect
            await handler._callbacks.close()

    return app


def _find_free_port(host: str, start_port: int, max_attempts: int = 10) -> int:
    """Find a free port starting from *start_port*."""
    import socket

    for offset in range(max_attempts):
        port = start_port + offset
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            logger.debug("port_in_use", port=port)
    raise RuntimeError(f"No free port found in range {start_port}-{start_port + max_attempts - 1}")


def _run_exec_mode(script_path: str) -> int:
    """Execute a Python script using the embedded interpreter.

    Used by ProcessSandbox when running inside a PyInstaller bundle
    (see RFC_2026-04_sandbox_frozen_exec.md). Returns the exit code the
    script propagates via ``sys.exit``.
    """
    import runpy

    try:
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        return 0 if code is None else 1
    return 0


def main() -> None:
    """CLI entry point: ``python -m ds_agent.api.app``."""
    import argparse

    parser = argparse.ArgumentParser(description="DS Agent API server")
    parser.add_argument(
        "--mode",
        choices=["server", "exec"],
        default="server",
        help="server: run FastAPI backend (default). exec: run SCRIPT with "
        "embedded Python (used by ProcessSandbox in frozen bundles).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18790)
    parser.add_argument(
        "script",
        nargs="?",
        help="Python script to execute when --mode exec. Ignored otherwise.",
    )
    args = parser.parse_args()

    if args.mode == "exec":
        if not args.script:
            sys.stderr.write("--mode exec requires a SCRIPT path argument\n")
            sys.exit(2)
        sys.exit(_run_exec_mode(args.script))

    import uvicorn

    # Find a free port (avoids crash when previous process still holds the port)
    port = _find_free_port(args.host, args.port)

    # SEC-01: Generate one-time token for WebSocket auth
    ws_token = os.environ.get("DS_AGENT_WS_TOKEN") or secrets.token_hex(32)

    app = create_app(ws_token=ws_token)
    app.state.port = port
    # Defer READY emission to lifespan.startup so Electron only sees READY
    # once the listening socket is up (avoids /health race on slow machines).
    app.state.emit_ready = True

    uvicorn.run(app, host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
