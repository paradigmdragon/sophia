from __future__ import annotations

import json
import re
from typing import Any

from core.ai.contracts import CONTRACT_MODELS
from core.ai.providers.base import BaseProvider, ProviderResult
from core.llm_interface import LLMInterface


def _extract_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._llm = LLMInterface()

    def run(self, task: str, payload: dict) -> ProviderResult:
        model_cls = CONTRACT_MODELS.get(task)
        if model_cls is None:
            return ProviderResult(provider=self.name, ok=False, error=f"unsupported task: {task}")

        schema = model_cls.model_json_schema()
        system_prompt = "\n".join(
            [
                "You are Sophia AI processor.",
                "Return JSON object only.",
                "No markdown, no explanation.",
                "Match the provided contract schema exactly.",
            ]
        )
        user_prompt = "\n".join(
            [
                "[task]",
                task,
                "",
                "[schema]",
                json.dumps(schema, ensure_ascii=False),
                "",
                "[input]",
                json.dumps(payload, ensure_ascii=False),
            ]
        )
        raw = self._llm._call_ollama(self._llm.primary_model, system_prompt, user_prompt)
        if not raw:
            return ProviderResult(provider=self.name, ok=False, error="empty_response")
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            return ProviderResult(provider=self.name, ok=False, error="invalid_json_response")
        return ProviderResult(provider=self.name, ok=True, data=parsed)
