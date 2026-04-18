"""Local model discovery for OpenAI-compatible servers (vLLM, SGLang, etc.)."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Default endpoints
VLLM_DEFAULT_URL = "http://127.0.0.1:8000/v1"
SGLANG_DEFAULT_URL = "http://127.0.0.1:30000/v1"


async def _fetch_json(url: str, timeout: float = 5.0) -> dict:
    """Fetch JSON from URL with timeout."""
    try:
        import aiohttp

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp,
        ):
            return dict(await resp.json())
    except ImportError:
        import json
        import urllib.request

        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return dict(json.loads(resp.read().decode()))


async def discover_openai_compatible_models(
    base_url: str,
    api_key: str | None = None,
) -> list[str]:
    """Discover models from an OpenAI-compatible /models endpoint.

    Works with vLLM, SGLang, LM Studio, and similar servers.
    """
    try:
        url = f"{base_url.rstrip('/')}/models"
        data = await _fetch_json(url)
        models = data.get("data", [])
        return [m["id"] for m in models if "id" in m]
    except Exception as e:
        logger.debug("local_discovery_failed", url=base_url, error=str(e))
        return []


async def discover_all_local_servers() -> dict[str, list[str]]:
    """Scan all known local server endpoints and return discovered models.

    Returns dict mapping server type to list of model IDs.
    """
    results: dict[str, list[str]] = {}

    # Ollama
    try:
        from ds_agent.providers.ollama import OllamaClient

        client = OllamaClient()
        if await client.is_running():
            models = await client.list_models()
            if models:
                results["ollama"] = [m["name"] for m in models]
    except Exception:
        pass

    # vLLM
    vllm_models = await discover_openai_compatible_models(VLLM_DEFAULT_URL)
    if vllm_models:
        results["vllm"] = vllm_models

    # SGLang
    sglang_models = await discover_openai_compatible_models(SGLANG_DEFAULT_URL)
    if sglang_models:
        results["sglang"] = sglang_models

    return results
