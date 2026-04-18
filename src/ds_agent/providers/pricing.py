"""Model pricing tracker."""

from __future__ import annotations

from dataclasses import dataclass, field

from ds_agent.domain.entities.messages import Usage

# Known model pricing (USD per 1M tokens) - 2026-04
KNOWN_PRICING: dict[str, dict[str, float]] = {
    # Anthropic (current)
    "claude-opus-4-6": {"input": 5.0, "output": 25.0, "cache_read": 0.5},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "cache_read": 0.1},
    # Anthropic (legacy)
    "claude-opus-4": {"input": 15.0, "output": 75.0, "cache_read": 1.5},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-haiku-3.5": {"input": 0.8, "output": 4.0, "cache_read": 0.08},
    # OpenAI (current)
    "gpt-5.4": {"input": 2.5, "output": 15.0},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.5},
    "gpt-5.4-nano": {"input": 0.2, "output": 1.25},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-4.1-mini": {"input": 0.4, "output": 1.6},
    "gpt-4.1-nano": {"input": 0.1, "output": 0.4},
    # OpenAI (legacy)
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "o1": {"input": 15.0, "output": 60.0},
    "o3": {"input": 10.0, "output": 40.0},
    "o3-mini": {"input": 1.1, "output": 4.4},
    "o4-mini": {"input": 1.1, "output": 4.4},
    # Chinese providers
    "deepseek/deepseek-chat": {"input": 0.28, "output": 0.42},
    "deepseek/deepseek-reasoner": {"input": 0.55, "output": 2.19},
    "minimax/MiniMax-M2.5": {"input": 0.118, "output": 0.99},
    "qwen/qwen3.6-plus-preview": {"input": 0.0, "output": 0.0},
    "qwen/qwen3.5-plus": {"input": 0.42, "output": 1.56},
    "zhipu/glm-5": {"input": 0.72, "output": 2.30},
    "moonshot/kimi-k2.5": {"input": 0.60, "output": 2.50},
    # Groq (fast inference)
    "groq/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "groq/qwen3-32b": {"input": 0.34, "output": 0.40},
    "groq/llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    # Open Source (Cloud)
    "together_ai/meta-llama/Llama-3.3-70B": {"input": 0.88, "output": 0.88},
}

DEFAULT_PRICING: dict[str, float] = {"input": 1.0, "output": 3.0}


@dataclass
class CostEntry:
    model: str
    usage: Usage
    cost_usd: float


@dataclass
class PricingTracker:
    """Track model pricing over one agent run."""

    history: list[CostEntry] = field(default_factory=list)
    total_cost_usd: float = 0.0

    def calculate_cost(self, model: str, usage: Usage) -> float:
        """Calculate one call cost in USD."""
        pricing = self._resolve_pricing(model)

        input_tokens = usage.input_tokens or 0
        output_tokens = usage.output_tokens or 0
        cache_read = usage.cache_read_tokens or 0
        reasoning = usage.reasoning_tokens or 0

        input_cost = (input_tokens / 1_000_000) * pricing.get("input", DEFAULT_PRICING["input"])
        output_cost = (output_tokens / 1_000_000) * pricing.get("output", DEFAULT_PRICING["output"])
        cache_cost = (cache_read / 1_000_000) * pricing.get(
            "cache_read", pricing.get("input", 0) * 0.1
        )
        reasoning_cost = (reasoning / 1_000_000) * pricing.get("output", DEFAULT_PRICING["output"])

        return input_cost + output_cost + cache_cost + reasoning_cost

    def track(self, model: str, usage: Usage) -> float:
        """Calculate and persist one pricing event."""
        cost = self.calculate_cost(model, usage)
        self.history.append(CostEntry(model=model, usage=usage, cost_usd=cost))
        self.total_cost_usd += cost
        return cost

    def get_summary(self) -> dict:
        """Return cumulative pricing totals and token usage."""
        by_model: dict[str, float] = {}
        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0
        reasoning_tokens = 0
        cache_savings_usd = 0.0
        for entry in self.history:
            by_model[entry.model] = by_model.get(entry.model, 0) + entry.cost_usd
            input_tokens += entry.usage.input_tokens or 0
            output_tokens += entry.usage.output_tokens or 0
            cache_read_tokens += entry.usage.cache_read_tokens or 0
            cache_write_tokens += entry.usage.cache_write_tokens or 0
            reasoning_tokens += entry.usage.reasoning_tokens or 0
            cache_savings_usd += self._calculate_cache_savings(entry.model, entry.usage)
        return {
            "total_cost_usd": self.total_cost_usd,
            "call_count": len(self.history),
            "by_model": by_model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "cache_write_tokens": cache_write_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cache_savings_usd": cache_savings_usd,
        }

    def _resolve_pricing(self, model: str) -> dict[str, float]:
        """Resolve pricing by exact, shortened, or partial model id."""
        if model in KNOWN_PRICING:
            return KNOWN_PRICING[model]

        if "/" in model:
            short_name = model.split("/", 1)[1]
            if short_name in KNOWN_PRICING:
                return KNOWN_PRICING[short_name]
            for known in KNOWN_PRICING:
                if short_name.startswith(known):
                    return KNOWN_PRICING[known]

        for known, pricing in KNOWN_PRICING.items():
            if known in model:
                return pricing

        return DEFAULT_PRICING

    def _calculate_cache_savings(self, model: str, usage: Usage) -> float:
        pricing = self._resolve_pricing(model)
        input_price = pricing.get("input", DEFAULT_PRICING["input"])
        cache_read_price = pricing.get("cache_read", input_price * 0.1)
        cached_tokens = usage.cache_read_tokens or 0
        if cached_tokens <= 0:
            return 0.0
        return max(input_price - cache_read_price, 0.0) * (cached_tokens / 1_000_000)
