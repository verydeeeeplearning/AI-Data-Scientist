from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from ds_agent.infrastructure.external.slack_connector import SlackConnector, SlackMessageRequest


class _SlackHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, object]]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        self.__class__.requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": json.loads(body),
            }
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:
        return


def test_slack_connector_posts_expected_payload() -> None:
    _SlackHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connector = SlackConnector()
        result = connector.dispatch(
            SlackMessageRequest(
                webhook_url=f"http://127.0.0.1:{server.server_port}/slack-webhook",
                text_fallback="Churn brief ready",
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}],
                channel="growth-ds",
                thread_ts="171234.0001",
            ),
            idempotency_key="wo_WO-2026-001:slack:post_message:abc123",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.system == "slack"
    assert result.external_ref.resource_id == "wo_WO-2026-001:slack:post_message:abc123"
    assert _SlackHandler.requests[0]["path"] == "/slack-webhook"
    assert _SlackHandler.requests[0]["body"] == {
        "text": "Churn brief ready",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}],
    }
