from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from ds_agent.infrastructure.external.confluence_connector import (
    ConfluenceConnector,
    ConfluencePageRequest,
)


class _ConfluenceHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, object]]] = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
        payload = json.loads(body)
        self.__class__.requests.append(
            {
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": payload,
            }
        )
        self.send_response(200 if self.path.endswith("/label") else 201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.path.endswith("/label"):
            response = {"results": payload}
        else:
            response = {
                "id": "1234",
                "title": payload["title"],
                "_links": {"webui": "/wiki/spaces/DS/pages/1234"},
            }
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        return


def test_confluence_connector_posts_storage_format_and_labels() -> None:
    _ConfluenceHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ConfluenceHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connector = ConfluenceConnector()
        result = connector.dispatch(
            ConfluencePageRequest(
                base_url=f"http://127.0.0.1:{server.server_port}",
                email="bot@example.com",
                api_token="secret",
                space_key="DS",
                title="Q2 Churn Brief",
                markdown_body="# Summary\n- Retention offer",
                parent_page_id="42",
                labels=["ds-agent", "wo-wo-2026-001"],
            ),
            idempotency_key="wo_WO-2026-001:confluence:publish_page:abc123",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    expected_auth = "Basic " + base64.b64encode(b"bot@example.com:secret").decode("ascii")
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.system == "confluence"
    assert result.external_ref.resource_id == "1234"
    assert result.external_ref.url == f"http://127.0.0.1:{server.server_port}/wiki/spaces/DS/pages/1234"
    assert _ConfluenceHandler.requests[0]["path"] == "/rest/api/content"
    assert _ConfluenceHandler.requests[0]["headers"]["Authorization"] == expected_auth
    assert _ConfluenceHandler.requests[0]["body"]["space"]["key"] == "DS"
    assert _ConfluenceHandler.requests[0]["body"]["ancestors"] == [{"id": "42"}]
    assert (
        _ConfluenceHandler.requests[0]["body"]["body"]["storage"]["value"]
        == "<h1>Summary</h1><ul><li>Retention offer</li></ul>"
    )
    assert _ConfluenceHandler.requests[1]["path"] == "/rest/api/content/1234/label"
    assert _ConfluenceHandler.requests[1]["body"] == [
        {"prefix": "global", "name": "ds-agent"},
        {"prefix": "global", "name": "wo-wo-2026-001"},
    ]
