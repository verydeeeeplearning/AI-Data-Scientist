"""Tests for the thin Telegram Bot API client."""

from __future__ import annotations

import json

import httpx
import pytest

from ds_agent.infrastructure.telegram import (
    BotIdentity,
    TelegramApiClient,
    TelegramApiError,
    TelegramAuthError,
    TelegramNetworkError,
)


def _json_response(status_code: int, payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(status_code, json=payload)


@pytest.mark.asyncio
async def test_get_me_success_returns_bot_identity() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            200,
            {
                "ok": True,
                "result": {
                    "id": 123456789,
                    "is_bot": True,
                    "first_name": "DS Agent",
                    "username": "ds_agent_bot",
                },
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("123456:test-token", http_client=http_client)

    identity = await client.get_me()

    assert identity == BotIdentity(
        id=123456789,
        username="ds_agent_bot",
        first_name="DS Agent",
    )
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/bot123456:test-token/getMe"

    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_me_401_raises_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            401,
            {
                "ok": False,
                "error_code": 401,
                "description": "Unauthorized",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("bad-token", http_client=http_client)

    with pytest.raises(TelegramAuthError) as exc_info:
        await client.get_me()

    assert exc_info.value.telegram_error_code == 401
    assert exc_info.value.description == "Unauthorized"

    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_me_api_error_preserves_telegram_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("123456:test-token", http_client=http_client)

    with pytest.raises(TelegramApiError) as exc_info:
        await client.get_me()

    assert exc_info.value.telegram_error_code == 429
    assert exc_info.value.description == "Too Many Requests"
    assert exc_info.value.status_code == 429

    await http_client.aclose()


@pytest.mark.asyncio
async def test_get_me_network_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("123456:test-token", http_client=http_client)

    with pytest.raises(TelegramNetworkError) as exc_info:
        await client.get_me()

    assert "Telegram getMe request failed" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)

    await http_client.aclose()


@pytest.mark.asyncio
async def test_send_message_posts_chat_id_and_text() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(
            200,
            {
                "ok": True,
                "result": {"message_id": 42},
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("123456:test-token", http_client=http_client)

    await client.send_message("987654321", "Pairing test")

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/bot123456:test-token/sendMessage"
    assert json.loads(requests[0].content) == {
        "chat_id": "987654321",
        "text": "Pairing test",
    }

    await http_client.aclose()


@pytest.mark.asyncio
async def test_send_message_ok_false_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            400,
            {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat not found",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramApiClient("123456:test-token", http_client=http_client)

    with pytest.raises(TelegramApiError) as exc_info:
        await client.send_message("missing", "hello")

    assert exc_info.value.telegram_error_code == 400
    assert exc_info.value.description == "Bad Request: chat not found"

    await http_client.aclose()
