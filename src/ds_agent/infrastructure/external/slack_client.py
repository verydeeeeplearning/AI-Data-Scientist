"""Slack webhook client."""

from __future__ import annotations

import json
from urllib import request


class SlackClient:
    """Send simple Slack webhook messages."""

    @staticmethod
    def build_payload(
        text: str, blocks: list[dict[str, object]] | None = None
    ) -> dict[str, object]:
        payload: dict[str, object] = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        return payload

    def send(
        self,
        webhook_url: str,
        *,
        text: str,
        blocks: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        payload = self.build_payload(text, blocks)
        req = request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        return {"ok": True, "response": body}
