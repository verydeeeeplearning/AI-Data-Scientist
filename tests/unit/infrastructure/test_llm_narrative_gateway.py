from __future__ import annotations

from dataclasses import dataclass

import pytest

from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.infrastructure.delivery import LLMNarrativeGateway

_VALID_NARRATIVE_JSON = """
```json
{
  "blocks": [
    {
      "section": "summary",
      "title": "Summary",
      "body_md": "Revenue risk increased by 4%.",
      "citations": ["lineage-1"]
    }
  ],
  "overall_tone": "decisive",
  "flagged_claims": []
}
```
"""


@dataclass
class FakeProvider:
    response_text: str
    model_id: str = "gpt-5.4"
    provider_name: str = "openai"
    last_messages: list | None = None
    last_kwargs: dict[str, object] | None = None

    async def chat(self, messages, **kwargs):
        self.last_messages = messages
        self.last_kwargs = kwargs
        return LLMResponse(content=self.response_text, model=self.model_id, usage=Usage())

    async def count_tokens(self, messages) -> int:
        return 0

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            provider=self.provider_name,
            display_name="Test Narrative Model",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )


@pytest.mark.asyncio
async def test_llm_narrative_gateway_parses_fenced_json_and_uses_openai_json_mode() -> None:
    provider = FakeProvider(_VALID_NARRATIVE_JSON, model_id="gpt-5.4", provider_name="openai")

    payload = await LLMNarrativeGateway(provider).generate(
        system_prompt="Write for executives.",
        user_prompt="Render the artifact.",
    )

    assert payload["blocks"][0]["section"] == "summary"
    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    assert provider.last_messages is not None
    assert "NarrativeBlocks" in (provider.last_messages[0].content or "")


@pytest.mark.asyncio
async def test_llm_narrative_gateway_uses_low_reasoning_effort_for_openai_reasoning_models(
) -> None:
    provider = FakeProvider(_VALID_NARRATIVE_JSON, model_id="o3", provider_name="openai")

    await LLMNarrativeGateway(provider).generate(
        system_prompt="Write for executives.",
        user_prompt="Render the artifact.",
    )

    assert provider.last_kwargs is not None
    assert provider.last_kwargs["response_format"] == {"type": "json_object"}
    assert provider.last_kwargs["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_llm_narrative_gateway_disables_anthropic_thinking() -> None:
    provider = FakeProvider(
        _VALID_NARRATIVE_JSON,
        model_id="claude-sonnet-4-6",
        provider_name="anthropic",
    )

    await LLMNarrativeGateway(provider).generate(
        system_prompt="Write for auditors.",
        user_prompt="Render the artifact.",
    )

    assert provider.last_kwargs is not None
    assert provider.last_kwargs["thinking"] is False
    assert "response_format" not in provider.last_kwargs
