from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMSettings:
    api_key: str | None
    model_replanner: str
    timeout_seconds: float
    prompt_variant: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def load_llm_settings() -> LLMSettings:
    timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "8")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError:
        timeout_seconds = 8.0
    prompt_variant = os.getenv("LLM_PROMPT_VARIANT", "A").strip().upper()
    if prompt_variant not in {"A", "B"}:
        prompt_variant = "A"
    return LLMSettings(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_replanner=os.getenv("LLM_MODEL_REPLANNER", "gpt-4o-mini"),
        timeout_seconds=max(2.0, timeout_seconds),
        prompt_variant=prompt_variant,
    )
