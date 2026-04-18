"""Request DTOs for evaluation use cases."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.domain.entities.gold_task import GoldTask


class EvalBatchRequest(BaseModel):
    """Input payload for batch evaluation."""

    model_config = ConfigDict(frozen=True)

    suite_name: str = Field(default="gold", min_length=1)
    tasks: tuple[GoldTask, ...]
    mode: Literal["offline", "shadow", "online"] = "offline"
    concurrency: int = Field(default=1, ge=1)
    scorer_filters: tuple[str, ...] = Field(default_factory=tuple)

