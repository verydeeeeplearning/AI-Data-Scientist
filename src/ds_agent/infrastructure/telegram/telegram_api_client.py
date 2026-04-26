"""Thin async client for the Telegram Bot API calls used by setup flows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import httpx

from ds_agent.application.ports.telegram_transport_port import BotIdentity
from ds_agent.domain.errors.telegram_errors import (
    TelegramApiError,
    TelegramAuthError,
    TelegramNetworkError,
)

_TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramApiClient:
    """Minimal async Telegram Bot API client for validation and test sends."""

    def __init__(
        self,
        token: str = "",
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._token = token.strip()
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient(timeout=timeout)

    async def get_me(self, token: str | None = None) -> BotIdentity:
        """Return the bot identity for the configured or supplied token."""

        payload = await self._request("GET", "getMe", token=token)
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise TelegramApiError(
                "Malformed Telegram getMe response: missing result",
                status_code=200,
            )

        return self._parse_bot_identity(result)

    async def send_message(
        self,
        chat_id: str | None = None,
        text: str | None = None,
        *,
        token: str | None = None,
    ) -> None:
        """Send a plain text message to a Telegram chat."""

        if chat_id is None or text is None:
            raise ValueError("chat_id and text are required")
        await self._request(
            "POST",
            "sendMessage",
            token=token,
            json={"chat_id": str(chat_id), "text": text},
        )

    async def aclose(self) -> None:
        """Close the owned HTTP client, if this adapter created one."""

        if self._owns_http_client:
            await self._http_client.aclose()

    async def _request(
        self,
        http_method: str,
        api_method: str,
        *,
        token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, object]:
        resolved_token = (token or self._token).strip()
        if not resolved_token:
            raise TelegramAuthError(
                "Telegram bot token must be non-empty",
                description="missing_token",
            )
        try:
            response = await self._http_client.request(
                http_method,
                self._url_for(api_method, resolved_token),
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise TelegramNetworkError(f"Telegram {api_method} request failed: {exc}") from exc

        payload = self._decode_payload(response, api_method)
        self._raise_for_telegram_error(payload, response, api_method)
        return payload

    @staticmethod
    def _url_for(api_method: str, token: str) -> str:
        return f"{_TELEGRAM_API_BASE}/bot{token}/{api_method}"

    def _decode_payload(
        self,
        response: httpx.Response,
        api_method: str,
    ) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError as exc:
            description = (
                f"Telegram {api_method} returned a non-JSON response"
                if not response.text
                else response.text
            )
            self._raise_api_error(
                description,
                telegram_error_code=response.status_code,
                status_code=response.status_code,
                cause=exc,
            )

        if not isinstance(payload, dict):
            raise TelegramApiError(
                f"Telegram {api_method} returned a malformed response",
                status_code=response.status_code,
            )
        return cast("dict[str, object]", payload)

    def _raise_for_telegram_error(
        self,
        payload: Mapping[str, object],
        response: httpx.Response,
        api_method: str,
    ) -> None:
        ok = payload.get("ok")
        if response.status_code < 400 and ok is True:
            return

        telegram_error_code = self._extract_error_code(payload, response.status_code)
        description = self._extract_description(payload, api_method, response)
        self._raise_api_error(
            description,
            telegram_error_code=telegram_error_code,
            status_code=response.status_code,
        )

    def _raise_api_error(
        self,
        description: str,
        *,
        telegram_error_code: int | None,
        status_code: int,
        cause: BaseException | None = None,
    ) -> None:
        error_type = (
            TelegramAuthError
            if telegram_error_code == 401 or status_code == 401
            else TelegramApiError
        )
        exc = error_type(
            description,
            telegram_error_code=telegram_error_code,
            description=description,
            status_code=status_code,
        )
        if cause is not None:
            raise exc from cause
        raise exc

    @staticmethod
    def _extract_error_code(
        payload: Mapping[str, object],
        status_code: int,
    ) -> int | None:
        raw_error_code = payload.get("error_code")
        if isinstance(raw_error_code, int) and not isinstance(raw_error_code, bool):
            return raw_error_code
        if status_code >= 400:
            return status_code
        return None

    @staticmethod
    def _extract_description(
        payload: Mapping[str, object],
        api_method: str,
        response: httpx.Response,
    ) -> str:
        description = payload.get("description")
        if isinstance(description, str) and description.strip():
            return description
        if response.status_code >= 400:
            return f"Telegram {api_method} failed with HTTP {response.status_code}"
        return f"Telegram {api_method} returned ok=false"

    @staticmethod
    def _parse_bot_identity(result: Mapping[str, object]) -> BotIdentity:
        bot_id = result.get("id")
        first_name = result.get("first_name")
        username = result.get("username")

        if not isinstance(bot_id, int) or isinstance(bot_id, bool):
            raise TelegramApiError("Malformed Telegram getMe response: invalid id")
        if not isinstance(first_name, str):
            raise TelegramApiError("Malformed Telegram getMe response: invalid first_name")
        if not isinstance(username, str) or not username.strip():
            raise TelegramApiError("Malformed Telegram getMe response: invalid username")

        return BotIdentity(
            id=bot_id,
            username=username,
            first_name=first_name,
        )
