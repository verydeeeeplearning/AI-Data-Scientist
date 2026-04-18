"""Minimal GitHub pull request client."""

from __future__ import annotations

import json
from urllib import request


class GitClient:
    """Create pull requests through the GitHub REST API."""

    @staticmethod
    def build_pr_payload(
        *,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, object]:
        return {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }

    def create_pull_request(
        self,
        *,
        repository: str,
        token: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict[str, object]:
        payload = self.build_pr_payload(title=title, body=body, head=head, base=base)
        req = request.Request(
            f"https://api.github.com/repos/{repository}/pulls",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body_text = response.read().decode("utf-8")
        parsed = json.loads(body_text)
        return parsed if isinstance(parsed, dict) else {"response": body_text}
