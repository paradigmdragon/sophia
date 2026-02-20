from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from core.ai.contracts import CONTRACT_MODELS, FALLBACK_BUILDERS


def _parse_json_candidate(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
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


def fallback_contract(task: str) -> dict[str, Any]:
    builder = FALLBACK_BUILDERS.get(task)
    if builder is None:
        raise KeyError(f"unsupported ai task: {task}")
    return builder()


def validate_contract(task: str, candidate: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    model = CONTRACT_MODELS.get(task)
    if model is None:
        raise KeyError(f"unsupported ai task: {task}")

    parsed = _parse_json_candidate(candidate)
    if parsed is None:
        return fallback_contract(task), {
            "pass": True,
            "reason": "parse_failed",
            "fallback_applied": True,
            "validation_errors": ["candidate is not valid JSON object"],
        }

    try:
        validated = model.model_validate(parsed)
        return validated.model_dump(by_alias=True), {
            "pass": True,
            "reason": "",
            "fallback_applied": False,
            "validation_errors": [],
        }
    except ValidationError as exc:
        errors = [err.get("msg", "validation error") for err in exc.errors()]
        return fallback_contract(task), {
            "pass": True,
            "reason": "schema_validation_failed",
            "fallback_applied": True,
            "validation_errors": errors[:5],
        }
