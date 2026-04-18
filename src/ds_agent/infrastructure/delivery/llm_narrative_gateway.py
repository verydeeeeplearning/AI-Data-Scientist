"""Provider-backed narrative generation adapter for stakeholder artifacts."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.interfaces.delivery import NarrativeGenerationPort
from ds_agent.domain.interfaces.llm_provider import LLMProvider

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.IGNORECASE | re.DOTALL)


class LLMNarrativeGateway(NarrativeGenerationPort):
    """Generate NarrativeBlocks-compatible JSON through the active LLM provider."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        temperature: float = 0.0,
        max_tokens: int = 1_600,
    ) -> None:
        self._provider = provider
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(self, *, system_prompt: str, user_prompt: str) -> Any:
        model_info = self._provider.get_model_info()
        provider_chat = cast(Any, self._provider).chat
        response = await provider_chat(
            self._build_messages(system_prompt, user_prompt, model_info=model_info),
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            **self._chat_kwargs(model_info),
        )
        return self._extract_json_payload(response.content)

    @staticmethod
    def _build_messages(
        system_prompt: str,
        user_prompt: str,
        *,
        model_info: ModelInfo,
    ) -> list[ChatMessage]:
        profile = LLMNarrativeGateway._prompt_profile(model_info)
        system_parts = [
            system_prompt,
            (
                "You are the DS Agent stakeholder narrative generator. "
                "Return only one compact JSON object compatible with NarrativeBlocks."
            ),
            (
                "Schema requirements: `blocks` must be a non-empty array of objects with "
                "`section`, `title`, `body_md`, and optional `citations`; also include "
                "`overall_tone` and optional `flagged_claims`."
            ),
            LLMNarrativeGateway._profile_instruction(profile),
        ]
        return [
            ChatMessage(role=Role.SYSTEM, content="\n\n".join(system_parts)),
            ChatMessage(role=Role.USER, content=user_prompt),
        ]

    @staticmethod
    def _prompt_profile(model_info: ModelInfo) -> str:
        provider = model_info.provider.lower()
        model_id = model_info.model_id.lower()
        if provider == "anthropic" or model_id.startswith("claude"):
            return "anthropic_json"
        if provider == "openai" or model_id.startswith(("gpt-", "o1", "o3", "o4")):
            return "openai_json"
        return "generic_json"

    @staticmethod
    def _profile_instruction(profile: str) -> str:
        if profile == "anthropic_json":
            return (
                "Anthropic profile: start directly with `{`, avoid any preamble, "
                "and disable thinking-style prose."
            )
        if profile == "openai_json":
            return (
                "OpenAI profile: strict JSON mode, start at the opening brace and end "
                "at the final closing brace."
            )
        return "Generic profile: emit a single JSON object and nothing else."

    @staticmethod
    def _chat_kwargs(model_info: ModelInfo) -> dict[str, object]:
        provider = model_info.provider.lower()
        model_id = model_info.model_id.lower()
        if provider == "anthropic" or model_id.startswith("claude"):
            return {"thinking": False}
        if provider == "openai" or model_id.startswith(("gpt-", "o1", "o3", "o4")):
            kwargs: dict[str, object] = {"response_format": {"type": "json_object"}}
            if model_id.startswith(("o1", "o3", "o4")):
                kwargs["reasoning_effort"] = "low"
            return kwargs
        return {}

    @staticmethod
    def _extract_json_payload(content: str | None) -> Any:
        if not content or not content.strip():
            raise ValueError("narrative gateway returned empty content")

        candidates: list[str] = [content.strip()]
        fenced = _FENCED_JSON_RE.search(content)
        if fenced:
            candidates.insert(0, fenced.group(1).strip())

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and start < end:
            candidates.append(content[start : end + 1].strip())

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return content.strip()
