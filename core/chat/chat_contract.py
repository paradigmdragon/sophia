from __future__ import annotations

from typing import Any

SCHEMA_NAME = "chat_contract.v0.1"
KINDS = ("ANSWER", "CLARIFY", "TASK_PLAN")
NEEDS_TYPES = ("meaning", "scope", "priority", "target", "timeframe")
EXECUTORS = ("local", "ide", "engine")


CHAT_CONTRACT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "kind",
        "text",
        "needs",
        "task_plan",
        "sources",
        "confidence_model",
    ],
    "properties": {
        "schema": {"type": "string", "const": SCHEMA_NAME},
        "kind": {"type": "string", "enum": list(KINDS)},
        "text": {"type": "string", "minLength": 1},
        "needs": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["type", "options"],
            "properties": {
                "type": {"type": "string", "enum": list(NEEDS_TYPES)},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 5,
                },
            },
        },
        "task_plan": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["steps"],
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["title", "executor", "inputs"],
                        "properties": {
                            "title": {"type": "string", "minLength": 1},
                            "executor": {"type": "string", "enum": list(EXECUTORS)},
                            "inputs": {"type": "object"},
                        },
                    },
                }
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "ref"],
                "properties": {
                    "type": {"type": "string", "enum": ["recent", "mind", "bitmap", "rules"]},
                    "ref": {"type": "string", "minLength": 1},
                },
            },
        },
        "confidence_model": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "allOf": [
        {
            "if": {"properties": {"kind": {"const": "CLARIFY"}}},
            "then": {
                "properties": {
                    "needs": {"type": "object"},
                },
            },
        },
        {
            "if": {"properties": {"kind": {"const": "TASK_PLAN"}}},
            "then": {
                "properties": {
                    "task_plan": {"type": "object"},
                },
            },
        },
        {
            "if": {"properties": {"kind": {"const": "ANSWER"}}},
            "then": {
                "properties": {
                    "sources": {"minItems": 1},
                },
            },
        },
    ],
}


def make_clarify_contract(
    *,
    text: str = "질문의 의미를 조금 더 구체적으로 설명해주실 수 있을까요?",
    needs_type: str = "meaning",
    options: list[str] | None = None,
    confidence_model: float = 0.0,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_NAME,
        "kind": "CLARIFY",
        "text": text,
        "needs": {
            "type": needs_type if needs_type in NEEDS_TYPES else "meaning",
            "options": [str(item) for item in (options or [])][:5],
        },
        "task_plan": None,
        "sources": [{"type": "recent", "ref": "fallback:clarify"}],
        "confidence_model": max(0.0, min(1.0, float(confidence_model))),
    }


def normalize_contract_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("schema", SCHEMA_NAME)
    out.setdefault("kind", "CLARIFY")
    out.setdefault("text", "질문의 의도를 확인할 수 있도록 조금 더 설명해주실 수 있을까요?")
    out.setdefault("needs", None)
    out.setdefault("task_plan", None)
    out.setdefault("sources", [])
    out.setdefault("confidence_model", 0.0)
    return out
