"""Minimal Jira REST client."""

from __future__ import annotations

import base64
import json
from urllib import request


class JiraClient:
    """Create Jira issues with basic-auth REST requests."""

    @staticmethod
    def build_issue_payload(
        *,
        project: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        assignee: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, object]:
        fields: dict[str, object] = {
            "project": {"key": project},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
        if assignee:
            fields["assignee"] = {"name": assignee}
        if priority:
            fields["priority"] = {"name": priority}
        if labels:
            fields["labels"] = labels
        return {"fields": fields}

    def create_issue(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        project: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        assignee: str | None = None,
        priority: str | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, object]:
        payload = self.build_issue_payload(
            project=project,
            summary=summary,
            description=description,
            issue_type=issue_type,
            assignee=assignee,
            priority=priority,
            labels=labels,
        )
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode("ascii")
        req = request.Request(
            f"{base_url.rstrip('/')}/rest/api/3/issue",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {token}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else {"response": body}
