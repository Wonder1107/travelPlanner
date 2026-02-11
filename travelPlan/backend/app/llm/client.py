from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

from app.llm.config import LLMSettings, load_llm_settings
from app.schemas import ReplanDecision


def _extract_json_text(raw: str) -> str:
    # 兼容模型偶发返回 ```json fenced code block 的情况。
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped


class LLMProvider:
    # 仅封装“重规划结构化决策”能力，避免与业务层耦合。
    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or load_llm_settings()
        self._client: Any | None = None
        if self.settings.enabled:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.settings.api_key,
                    timeout=self.settings.timeout_seconds,
                )
            except Exception:
                self._client = None
        self._prompt_cache: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def generate_structured_decision(
        self,
        context: dict[str, Any],
    ) -> tuple[ReplanDecision | None, dict[str, Any]]:
        """请求模型输出 ReplanDecision，并返回可观测 meta。

        若模型不可用/超时/解析失败，返回 (None, meta.error) 给上游触发 fallback。
        """
        started = perf_counter()
        meta: dict[str, Any] = {
            "model": self.settings.model_replanner,
            "latency_ms": None,
            "error": None,
            "prompt_variant": self.settings.prompt_variant,
        }
        if self._client is None:
            meta["error"] = "llm_disabled_or_client_init_failed"
            return None, meta

        try:
            system_prompt = self._load_replanner_prompt()
            payload = json.dumps(context, ensure_ascii=True)
            completion = self._client.chat.completions.create(
                model=self.settings.model_replanner,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            json_text = _extract_json_text(content)
            decision_data = json.loads(json_text)
            # 以 Pydantic 作为最终 schema 守门，防止字段缺失/类型漂移。
            decision = ReplanDecision.model_validate(decision_data)
            return decision, meta
        except Exception as exc:
            meta["error"] = str(exc)[:240]
            return None, meta
        finally:
            meta["latency_ms"] = int((perf_counter() - started) * 1000)

    def _load_replanner_prompt(self) -> str:
        # Prompt 本地缓存：避免频繁 IO，提升事件触发时响应速度。
        variant = self.settings.prompt_variant
        if variant in self._prompt_cache:
            return self._prompt_cache[variant]
        prompt_file = "replanner_system_b.md" if variant == "B" else "replanner_system.md"
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / prompt_file
        try:
            self._prompt_cache[variant] = prompt_path.read_text(encoding="utf-8")
        except Exception:
            self._prompt_cache[variant] = (
                "You are ReplanAgent. Return JSON only with: "
                "should_replan, primary_reason, selected_poi_id, alternatives, "
                "tradeoffs, user_message, confidence."
            )
        return self._prompt_cache[variant]
