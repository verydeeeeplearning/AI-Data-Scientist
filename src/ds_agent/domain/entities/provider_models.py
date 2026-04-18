"""Provider-related domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """모델 메타데이터."""

    model_id: str
    provider: str
    display_name: str
    max_context_tokens: int
    max_output_tokens: int
    supports_tools: bool = True
    supports_vision: bool = False
    supports_thinking: bool = False
    supports_caching: bool = False
    input_cost_per_mtok: float = 0.0
    output_cost_per_mtok: float = 0.0


@dataclass
class ProviderSDKConfig:
    """프로바이더 SDK 설정 (api_key, base_url, timeout 등 연결 파라미터)."""

    api_key: str | None = None
    base_url: str | None = None
    api_version: str | None = None
    timeout: float = 120.0
    max_retries: int = 3
    extra: dict = field(default_factory=dict)
