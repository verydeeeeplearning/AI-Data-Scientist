from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

from ds_agent.infrastructure.external.notion_connector import (
    NotionConnector,
    NotionPageRequest,
)


class _NotionHandler(BaseHTTPRequestHandler):
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
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {"id": "page_123", "url": "https://notion.so/page_123", "object": "page"}
            ).encode("utf-8")
        )

    def log_message(self, format: str, *args) -> None:
        return


def test_notion_connector_posts_expected_properties_and_blocks() -> None:
    _NotionHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _NotionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connector = NotionConnector()
        result = connector.dispatch(
            NotionPageRequest(
                token="secret-token",
                api_base_url=f"http://127.0.0.1:{server.server_port}/v1",
                title="Weekly Churn Brief",
                markdown_body="# Summary\n- Segment A",
                parent_page_id="parent-1",
                status="Draft",
                owner="Kim",
                quarter="2026-Q2",
                tags=["growth", "retention"],
            ),
            idempotency_key="wo_WO-2026-001:notion:publish_page:def456",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.success is True
    assert result.external_ref is not None
    assert result.external_ref.system == "notion"
    assert result.external_ref.resource_id == "page_123"
    assert result.external_ref.url == "https://notion.so/page_123"
    assert _NotionHandler.requests[0]["path"] == "/v1/pages"
    assert _NotionHandler.requests[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert _NotionHandler.requests[0]["headers"]["Notion-Version"] == "2022-06-28"
    assert _NotionHandler.requests[0]["body"]["parent"] == {"page_id": "parent-1"}
    assert (
        _NotionHandler.requests[0]["body"]["properties"]["title"]["title"][0]["text"]["content"]
        == "Weekly Churn Brief"
    )
    assert _NotionHandler.requests[0]["body"]["properties"]["Status"]["select"]["name"] == "Draft"
    assert (
        _NotionHandler.requests[0]["body"]["properties"]["Owner"]["rich_text"][0]["text"]["content"]
        == "Kim"
    )
    assert (
        _NotionHandler.requests[0]["body"]["properties"]["Quarter"]["rich_text"][0]["text"]["content"]
        == "2026-Q2"
    )
    assert _NotionHandler.requests[0]["body"]["properties"]["Tags"]["multi_select"] == [
        {"name": "growth"},
        {"name": "retention"},
    ]
    assert _NotionHandler.requests[0]["body"]["children"][0]["type"] == "heading_1"
    assert _NotionHandler.requests[0]["body"]["children"][1]["type"] == "bulleted_list_item"
