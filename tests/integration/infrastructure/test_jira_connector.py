from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from ds_agent.infrastructure.external.jira_connector import JiraConnector, JiraIssueRequest


class _JiraHandler(BaseHTTPRequestHandler):
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
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"key": "DS-123", "id": "1001"}).encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        return


def test_jira_connector_posts_expected_payload_and_auth() -> None:
    _JiraHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _JiraHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connector = JiraConnector()
        result = connector.dispatch(
            JiraIssueRequest(
                base_url=f"http://127.0.0.1:{server.server_port}",
                email="bot@example.com",
                api_token="secret",
                project_key="DS",
                summary="Follow up churn actions",
                description="Create retention ticket",
                issue_type="Task",
                labels=["ds-agent", "wo-wo-2026-001"],
            ),
            idempotency_key="wo_WO-2026-001:jira:create_issue:def456",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    expected_auth = "Basic " + base64.b64encode(b"bot@example.com:secret").decode("ascii")
    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.resource_id == "DS-123"
    assert result.external_ref.url == f"http://127.0.0.1:{server.server_port}/browse/DS-123"
    assert _JiraHandler.requests[0]["path"] == "/rest/api/3/issue"
    assert _JiraHandler.requests[0]["headers"]["Authorization"] == expected_auth
    assert _JiraHandler.requests[0]["body"]["fields"]["project"]["key"] == "DS"
    assert _JiraHandler.requests[0]["body"]["fields"]["labels"] == ["ds-agent", "wo-wo-2026-001"]
