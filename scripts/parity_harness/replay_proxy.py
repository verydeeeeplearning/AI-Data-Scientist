"""Local HTTP proxy that replays VCR cassettes for OpenAI chat.completions.

Purpose
-------
The S16 parity harness needs the packaged backend (``ds-agent-api.exe``)
to receive byte-identical LLM responses across 3 channels and 3
scenarios. Because the backend is a subprocess, VCR.py cannot intercept
its HTTP traffic directly. Instead we stand up a tiny HTTP server that
serves the recorded cassette responses when the backend calls into it
via ``OPENAI_BASE_URL=http://127.0.0.1:<port>/v1``.

Matching
--------
Each cassette has a single interaction (one request + one response).
The replay proxy fingerprints the *inbound* request body by its
``messages[-1].content`` (the scenario goal text) and routes to the
cassette whose recorded body contains the same content. If no cassette
matches, the proxy returns ``HTTP 424 Failed Dependency`` so the caller
knows replay was not satisfied — the harness surfaces this as a run
failure, matching the VCR.py ``record_mode="none"`` "never record"
guarantee.

This module is **replay-only**. It never makes outbound network calls,
never records new cassettes. If the backend's request schema changes
and breaks matching, the run fails fast — exactly what we want in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

logger = logging.getLogger("replay_proxy")

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CASSETTE_DIR = REPO / "tests" / "fixtures" / "llm_cassettes"


class CassetteStore:
    """In-memory index of cassettes, fingerprinted by the scenario goal text."""

    def __init__(self, cassette_dir: Path) -> None:
        self._cassettes: dict[str, dict[str, Any]] = {}
        self._by_user_content: dict[str, str] = {}  # user_content_stripped → cassette_name
        self._load(cassette_dir)

    def _load(self, cassette_dir: Path) -> None:
        if not cassette_dir.exists():
            raise FileNotFoundError(f"cassette directory missing: {cassette_dir}")
        for path in sorted(cassette_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            interactions = data.get("interactions") or []
            if not interactions:
                logger.warning("cassette %s has 0 interactions, skipping", path.name)
                continue
            interaction = interactions[0]  # single-interaction policy
            request_body_raw = interaction.get("request", {}).get("body") or ""
            user_content = _extract_user_content(request_body_raw)
            self._cassettes[path.name] = interaction
            if user_content:
                # Collapse whitespace for match robustness (JSON may insert
                # soft line breaks inside YAML quoted strings).
                key = " ".join(user_content.split())
                self._by_user_content[key] = path.name
            logger.info(
                "loaded cassette %s  user_content_preview=%r", path.name, user_content[:60]
            )

    def lookup(self, request_body: bytes) -> tuple[str | None, dict[str, Any] | None]:
        """Return (cassette_name, interaction) for a POST body, or (None, None)."""
        try:
            req = json.loads(request_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, None
        messages = req.get("messages") or []
        if not messages:
            return None, None
        # Pick the LAST user turn — production SDK may append conversation
        # history; we key off the freshest user utterance.
        user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_content = str(m.get("content") or "")
                break
        if not user_content:
            return None, None
        key = " ".join(user_content.split())
        cassette_name = self._by_user_content.get(key)
        if cassette_name is None:
            # Substring fallback: some SDK wrappers may inject preamble.
            for recorded_key, cname in self._by_user_content.items():
                if recorded_key in key or key in recorded_key:
                    cassette_name = cname
                    break
        if cassette_name is None:
            return None, None
        return cassette_name, self._cassettes[cassette_name]

    def list_loaded(self) -> list[str]:
        return sorted(self._cassettes.keys())


def _extract_user_content(raw_body: str) -> str:
    """Return the user-role content from a recorded JSON request body."""
    try:
        req = json.loads(raw_body)
    except (TypeError, json.JSONDecodeError):
        return ""
    messages = req.get("messages") or []
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


class _ProxyHandler(BaseHTTPRequestHandler):
    store: CassetteStore | None = None  # class-level injected
    stats: dict[str, Any] | None = None  # injected at server start

    # Silence default stderr request log — we write our own.
    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("http %s - - %s", self.address_string(), format % args)

    def _json(self, status: int, obj: dict, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        # Health probe for the harness.
        if self.path == "/__replay/health":
            assert self.store is not None
            self._json(200, {"ok": True, "cassettes": self.store.list_loaded()})
            return
        if self.path == "/__replay/stats":
            assert self.stats is not None
            self._json(200, dict(self.stats))
            return
        self._json(
            404,
            {"error": {"code": "not_found", "message": f"GET {self.path} not served by replay proxy"}},
        )

    def do_POST(self) -> None:
        assert self.store is not None and self.stats is not None
        content_length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(content_length) if content_length else b""

        self.stats["requests_received"] += 1

        # Only one endpoint served: /v1/chat/completions.
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self.stats["rejected_unknown_path"] += 1
            self._json(
                424,
                {
                    "error": {
                        "code": "replay_path_not_served",
                        "message": f"path {self.path} not in replay cassette set",
                    }
                },
            )
            return

        cassette_name, interaction = self.store.lookup(body)
        if interaction is None:
            self.stats["rejected_no_match"] += 1
            self._json(
                424,
                {
                    "error": {
                        "code": "replay_no_match",
                        "message": (
                            "no cassette matched the request body. record_mode=none — "
                            "new requests are NOT allowed. Re-record via "
                            "scripts/parity_harness/record_llm_cassettes.py."
                        ),
                    }
                },
            )
            return

        self.stats["served"] += 1
        self.stats["served_by_cassette"].setdefault(cassette_name, 0)
        self.stats["served_by_cassette"][cassette_name] += 1

        # Serve the recorded response with headers + body intact.
        resp = interaction.get("response", {}) or {}
        status_code = int(resp.get("status", {}).get("code", 200))
        # VCR stores body under response.body.string
        body_obj = resp.get("body", {}) or {}
        body_str = body_obj.get("string") or ""
        resp_body = body_str.encode("utf-8") if isinstance(body_str, str) else bytes(body_str)

        recorded_headers: dict[str, list[str]] = resp.get("headers", {}) or {}

        # Strip Transfer-Encoding: chunked since we're sending a known-size
        # body. Also strip Content-Encoding (VCR decoded the body for us via
        # decode_compressed_response=True during recording). Strip
        # Content-Length from recorded (we'll add our own accurate one).
        hop_by_hop = {
            "transfer-encoding",
            "content-encoding",
            "connection",
            "content-length",
        }

        self.send_response(status_code)
        for header_name, values in recorded_headers.items():
            if header_name.lower() in hop_by_hop:
                continue
            if not values:
                continue
            # Values are serialized as list-of-str; forward each.
            for v in values:
                if v == "REDACTED":
                    continue  # don't emit redacted headers at all
                self.send_header(header_name, v)
        self.send_header("Content-Length", str(len(resp_body)))
        self.send_header("X-Replay-Cassette", cassette_name)
        self.end_headers()
        self.wfile.write(resp_body)


class ReplayProxyServer:
    """Run the replay proxy in a background thread."""

    def __init__(self, cassette_dir: Path | None = None, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._requested_port = port
        self._cassette_dir = cassette_dir or DEFAULT_CASSETTE_DIR
        self._store = CassetteStore(self._cassette_dir)
        self._stats: dict[str, Any] = {
            "requests_received": 0,
            "served": 0,
            "rejected_no_match": 0,
            "rejected_unknown_path": 0,
            "served_by_cassette": {},
            "cassette_dir": str(self._cassette_dir),
            "loaded_cassettes": self._store.list_loaded(),
        }
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._actual_port: int | None = None

    @property
    def port(self) -> int:
        if self._actual_port is None:
            raise RuntimeError("server not started")
        return self._actual_port

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self.port}/v1"

    @property
    def stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def start(self) -> None:
        # Inject dependencies onto the handler class.
        _ProxyHandler.store = self._store
        _ProxyHandler.stats = self._stats

        self._server = ThreadingHTTPServer((self._host, self._requested_port), _ProxyHandler)
        # Resolve actual port after bind (requested_port=0 => OS-assigned).
        self._actual_port = self._server.server_address[1]

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.25},
            name="replay-proxy",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "replay proxy listening on http://%s:%d (cassettes=%s)",
            self._host,
            self._actual_port,
            self._store.list_loaded(),
        )

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> ReplayProxyServer:
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=0, help="127.0.0.1 port (0 = OS-assigned)")
    p.add_argument(
        "--cassette-dir", type=Path, default=DEFAULT_CASSETTE_DIR, help="cassette directory"
    )
    p.add_argument(
        "--foreground", action="store_true", help="block on the server (useful for manual testing)"
    )
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s  %(message)s")
    srv = ReplayProxyServer(cassette_dir=args.cassette_dir, port=args.port)
    srv.start()
    print(f"REPLAY_PROXY_URL={srv.base_url}")
    if not args.foreground:
        srv.stop()
        return 0
    try:
        asyncio.get_event_loop().run_until_complete(asyncio.Event().wait())
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
