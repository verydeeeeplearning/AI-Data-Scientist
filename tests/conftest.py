"""Root conftest — shared fixtures for all test levels."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.hooks import HookContext
from ds_agent.domain.entities.messages import LLMResponse
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.infrastructure.secrets.secret_storage import (
    InMemorySecretStorage,
    set_shared_secret_storage,
)

# ---------------------------------------------------------------------------
# LLM Provider mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_mock_provider():
    """Factory fixture: create a mock LLM provider that returns responses in sequence."""

    def _factory(responses: list[LLMResponse]) -> MagicMock:
        provider = MagicMock()
        provider.chat = AsyncMock(side_effect=responses)
        provider.count_tokens = AsyncMock(return_value=100)
        provider.get_model_info = MagicMock(
            return_value=ModelInfo(
                model_id="mock",
                provider="mock",
                display_name="Mock",
                max_context_tokens=128_000,
                max_output_tokens=4096,
            )
        )
        return provider

    return _factory


# ---------------------------------------------------------------------------
# Tool Registry mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_mock_tool_registry():
    """Factory fixture: create a mock tool registry with optional tool handlers."""

    def _factory(tools: dict | None = None) -> MagicMock:
        registry = MagicMock()
        tools = tools or {}

        def get_definitions():
            return [
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"Mock: {name}",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
                for name in tools
            ]

        async def dispatch(name, arguments):
            handler = tools.get(name)
            if handler:
                return str(handler(**arguments))
            return json.dumps({"error": f"Unknown tool: {name}"})

        registry.get_definitions = get_definitions
        registry.dispatch = AsyncMock(side_effect=dispatch)
        return registry

    return _factory


# ---------------------------------------------------------------------------
# HookContext mock
# ---------------------------------------------------------------------------


@pytest.fixture()
def make_hook_context():
    """Factory fixture: create a HookContext with sensible defaults."""

    def _factory(**overrides) -> HookContext:
        defaults = {
            "mode": "auto",
            "session_id": "test-session",
            "iteration": 1,
            "total_cost_usd": 0.0,
            "emit": MagicMock(),
        }
        defaults.update(overrides)
        return HookContext(**defaults)

    return _factory


@pytest.fixture(autouse=True)
def isolated_secret_storage():
    """Reset shared secret storage between tests."""
    set_shared_secret_storage(InMemorySecretStorage())
    try:
        yield
    finally:
        set_shared_secret_storage(None)
