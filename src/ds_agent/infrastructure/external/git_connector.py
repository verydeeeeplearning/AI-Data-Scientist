"""GitHub/GitLab pull-request connector for workflow integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from urllib import error, parse, request

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities.external_reference import ExternalReference
from ds_agent.infrastructure.external.connector_models import ConnectorHealthResult, ConnectorResult
from ds_agent.infrastructure.external.egress_guard import (
    is_egress_enabled,
    make_disabled_result,
)


class GitFileChange(BaseModel):
    """One file mutation to include in a git-backed review artifact."""

    model_config = ConfigDict(validate_assignment=True)

    path: str = Field(min_length=1)
    content_base64: str | None = None
    mode: Literal["add", "update", "delete"]

    @model_validator(mode="after")
    def _validate_content(self) -> GitFileChange:
        if self.mode != "delete" and not self.content_base64:
            raise ValueError("content_base64 is required for add/update git file changes")
        return self


class GitPRRequest(BaseModel):
    """Request payload for opening a GitHub PR or GitLab merge request."""

    provider: Literal["github", "gitlab"] = "github"
    api_base_url: str | None = None
    repository: str = Field(min_length=1)
    token: str = Field(min_length=1)
    base_branch: str = Field(min_length=1)
    head_branch: str = Field(min_length=1)
    pr_title: str = Field(min_length=1)
    pr_body_markdown: str = Field(min_length=1)
    files: list[GitFileChange] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    draft: bool = False
    commit_message: str | None = None


class GitConnector:
    """Create branch/file/PR workflows against GitHub or GitLab."""

    system_name = "git"

    def dispatch(
        self,
        request_model: GitPRRequest,
        *,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult:
        now = datetime.now(UTC)
        resource_type = (
            "pull_request" if request_model.provider == "github" else "merge_request"
        )
        if dry_run:
            return ConnectorResult(
                success=True,
                external_ref=ExternalReference(
                    system=request_model.provider,
                    resource_type=resource_type,
                    resource_id=idempotency_key,
                    metadata={
                        "dry_run": True,
                        "repository": request_model.repository,
                        "head_branch": request_model.head_branch,
                    },
                    created_at=now,
                    idempotency_key=idempotency_key,
                ),
            )
        # S14 in-adapter egress kill-switch (RC-5 closed).
        if not is_egress_enabled():
            code, msg = make_disabled_result()
            return ConnectorResult(
                success=False,
                error_code=code,
                error_message=msg,
                retriable=False,
            )
        try:
            if request_model.provider == "github":
                payload = self._dispatch_github(request_model)
                resource_id = str(payload.get("number") or payload.get("id") or idempotency_key)
                resource_url = str(payload.get("html_url") or "")
            else:
                payload = self._dispatch_gitlab(request_model)
                resource_id = str(payload.get("iid") or payload.get("id") or idempotency_key)
                resource_url = str(payload.get("web_url") or "")
        except Exception as exc:
            return ConnectorResult(
                success=False,
                error_code=type(exc).__name__.upper(),
                error_message=str(exc),
                retriable=True,
            )
        return ConnectorResult(
            success=True,
            external_ref=ExternalReference(
                system=request_model.provider,
                resource_type=resource_type,
                resource_id=resource_id,
                url=resource_url or None,
                metadata=payload,
                created_at=now,
                idempotency_key=idempotency_key,
            ),
        )

    def _dispatch_github(self, request_model: GitPRRequest) -> dict[str, Any]:
        api_base_url = (request_model.api_base_url or "https://api.github.com").rstrip("/")
        repo_path = f"/repos/{request_model.repository}"
        self._ensure_github_branch(api_base_url, repo_path, request_model)
        self._apply_github_changes(api_base_url, repo_path, request_model)
        payload = self._request_json(
            method="POST",
            url=f"{api_base_url}{repo_path}/pulls",
            token=request_model.token,
            payload={
                "title": request_model.pr_title,
                "body": request_model.pr_body_markdown,
                "head": request_model.head_branch,
                "base": request_model.base_branch,
                "draft": request_model.draft,
            },
            auth_header="Authorization",
            auth_value=f"Bearer {request_model.token}",
            extra_headers={"Accept": "application/vnd.github+json"},
        )
        if payload is None:
            raise ValueError("GitHub pull request response was empty")
        number = payload.get("number")
        if number and request_model.reviewers:
            self._request_json(
                method="POST",
                url=f"{api_base_url}{repo_path}/pulls/{number}/requested_reviewers",
                token=request_model.token,
                payload={"reviewers": request_model.reviewers},
                auth_header="Authorization",
                auth_value=f"Bearer {request_model.token}",
                extra_headers={"Accept": "application/vnd.github+json"},
            )
        if number and request_model.labels:
            self._request_json(
                method="POST",
                url=f"{api_base_url}{repo_path}/issues/{number}/labels",
                token=request_model.token,
                payload={"labels": request_model.labels},
                auth_header="Authorization",
                auth_value=f"Bearer {request_model.token}",
                extra_headers={"Accept": "application/vnd.github+json"},
            )
        return payload

    def _ensure_github_branch(
        self,
        api_base_url: str,
        repo_path: str,
        request_model: GitPRRequest,
    ) -> None:
        existing = self._request_json(
            method="GET",
            url=f"{api_base_url}{repo_path}/git/ref/heads/{request_model.head_branch}",
            token=request_model.token,
            payload=None,
            auth_header="Authorization",
            auth_value=f"Bearer {request_model.token}",
            extra_headers={"Accept": "application/vnd.github+json"},
            allow_not_found=True,
        )
        if existing is not None:
            return
        base_ref = self._request_json(
            method="GET",
            url=f"{api_base_url}{repo_path}/git/ref/heads/{request_model.base_branch}",
            token=request_model.token,
            payload=None,
            auth_header="Authorization",
            auth_value=f"Bearer {request_model.token}",
            extra_headers={"Accept": "application/vnd.github+json"},
        )
        if base_ref is None:
            raise ValueError("GitHub base branch response was empty")
        base_sha = str(base_ref.get("object", {}).get("sha") or "")
        if not base_sha:
            raise ValueError("GitHub base branch sha could not be resolved")
        self._request_json(
            method="POST",
            url=f"{api_base_url}{repo_path}/git/refs",
            token=request_model.token,
            payload={"ref": f"refs/heads/{request_model.head_branch}", "sha": base_sha},
            auth_header="Authorization",
            auth_value=f"Bearer {request_model.token}",
            extra_headers={"Accept": "application/vnd.github+json"},
        )

    def _apply_github_changes(
        self,
        api_base_url: str,
        repo_path: str,
        request_model: GitPRRequest,
    ) -> None:
        message = request_model.commit_message or f"feat(ds): {request_model.pr_title}"
        for change in request_model.files:
            encoded_path = parse.quote(change.path, safe="/")
            content_url = (
                f"{api_base_url}{repo_path}/contents/{encoded_path}"
                f"?ref={parse.quote(request_model.head_branch, safe='')}"
            )
            existing = self._request_json(
                method="GET",
                url=content_url,
                token=request_model.token,
                payload=None,
                auth_header="Authorization",
                auth_value=f"Bearer {request_model.token}",
                extra_headers={"Accept": "application/vnd.github+json"},
                allow_not_found=True,
            )
            if change.mode == "delete":
                if existing is None:
                    continue
                self._request_json(
                    method="DELETE",
                    url=f"{api_base_url}{repo_path}/contents/{encoded_path}",
                    token=request_model.token,
                    payload={
                        "message": message,
                        "branch": request_model.head_branch,
                        "sha": existing["sha"],
                    },
                    auth_header="Authorization",
                    auth_value=f"Bearer {request_model.token}",
                    extra_headers={"Accept": "application/vnd.github+json"},
                )
                continue
            payload: dict[str, Any] = {
                "message": message,
                "content": change.content_base64,
                "branch": request_model.head_branch,
            }
            if existing is not None and existing.get("sha"):
                payload["sha"] = existing["sha"]
            self._request_json(
                method="PUT",
                url=f"{api_base_url}{repo_path}/contents/{encoded_path}",
                token=request_model.token,
                payload=payload,
                auth_header="Authorization",
                auth_value=f"Bearer {request_model.token}",
                extra_headers={"Accept": "application/vnd.github+json"},
            )

    def _dispatch_gitlab(self, request_model: GitPRRequest) -> dict[str, Any]:
        api_base_url = (request_model.api_base_url or "https://gitlab.com/api/v4").rstrip("/")
        project = parse.quote(request_model.repository, safe="")
        self._request_json(
            method="POST",
            url=f"{api_base_url}/projects/{project}/repository/branches",
            token=request_model.token,
            payload={"branch": request_model.head_branch, "ref": request_model.base_branch},
            auth_header="PRIVATE-TOKEN",
            auth_value=request_model.token,
            allow_conflict=True,
        )
        if request_model.files:
            actions = []
            for change in request_model.files:
                action = "create" if change.mode == "add" else change.mode
                item: dict[str, Any] = {
                    "action": action,
                    "file_path": change.path,
                }
                if change.mode != "delete":
                    item["content"] = change.content_base64
                    item["encoding"] = "base64"
                actions.append(item)
            self._request_json(
                method="POST",
                url=f"{api_base_url}/projects/{project}/repository/commits",
                token=request_model.token,
                payload={
                    "branch": request_model.head_branch,
                    "commit_message": (
                        request_model.commit_message or f"feat(ds): {request_model.pr_title}"
                    ),
                    "actions": actions,
                },
                auth_header="PRIVATE-TOKEN",
                auth_value=request_model.token,
            )
        title = request_model.pr_title
        if request_model.draft and not title.lower().startswith("draft:"):
            title = f"Draft: {title}"
        payload: dict[str, Any] = {
            "source_branch": request_model.head_branch,
            "target_branch": request_model.base_branch,
            "title": title,
            "description": request_model.pr_body_markdown,
        }
        if request_model.labels:
            payload["labels"] = ",".join(request_model.labels)
        reviewer_ids = [
            int(value)
            for value in request_model.reviewers
            if str(value).isdigit()
        ]
        if reviewer_ids:
            payload["reviewer_ids"] = reviewer_ids
        merge_request = self._request_json(
            method="POST",
            url=f"{api_base_url}/projects/{project}/merge_requests",
            token=request_model.token,
            payload=payload,
            auth_header="PRIVATE-TOKEN",
            auth_value=request_model.token,
        )
        if merge_request is None:
            raise ValueError("GitLab merge request response was empty")
        return merge_request

    @staticmethod
    def _request_json(
        *,
        method: str,
        url: str,
        token: str,
        payload: Any,
        auth_header: str,
        auth_value: str,
        extra_headers: dict[str, str] | None = None,
        allow_not_found: bool = False,
        allow_conflict: bool = False,
    ) -> dict[str, Any] | None:
        del token
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", auth_header: auth_value}
        if extra_headers:
            headers.update(extra_headers)
        req = request.Request(url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=15) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            if allow_not_found and exc.code == 404:
                return None
            if allow_conflict and exc.code in {400, 409}:
                return {}
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"Git API error ({exc.code}): {detail}") from exc
        if not body:
            return {}
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError(f"Git API error: {parsed}")

    def health_check(self) -> ConnectorHealthResult:
        """Git connector is stateless per-request — report available."""
        return ConnectorHealthResult(
            system=self.system_name,
            healthy=True,
            message="Stateless connector available.",
            latency_ms=0.0,
        )
