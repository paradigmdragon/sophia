from __future__ import annotations

import json
import re
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from core.chat.chat_contract import (
    CHAT_CONTRACT_SCHEMA,
    NEEDS_TYPES,
    SCHEMA_NAME,
    make_clarify_contract,
    normalize_contract_defaults,
)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def parse_contract_json(raw: str) -> dict[str, Any] | None:
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


def _single_question(text: str) -> str:
    clean = " ".join((text or "").split())
    if not clean:
        return "질문의 의미를 조금 더 구체적으로 설명해주실 수 있을까요?"
    chunks = [part.strip() for part in clean.split("?") if part.strip()]
    if not chunks:
        return "질문의 의미를 조금 더 구체적으로 설명해주실 수 있을까요?"
    return f"{chunks[0]}?"


def _evidence_scope(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "none"
    types = {str(item.get("type", "")).strip().lower() for item in sources if isinstance(item, dict)}
    if len(types) >= 3:
        return "broad"
    if len(types) >= 2:
        return "medium"
    if len(types) == 1:
        return "narrow"
    return "none"


def _validation_errors(contract: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(CHAT_CONTRACT_SCHEMA)
    errors: list[str] = []
    for err in validator.iter_errors(contract):
        path = ".".join([str(item) for item in err.absolute_path])
        where = path or "root"
        errors.append(f"{where}: {err.message}")
    return errors


def validate_and_gate_contract(
    contract: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    parse_error: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ctx = context or {}
    normalized = normalize_contract_defaults(contract)
    normalized["schema"] = SCHEMA_NAME

    errors = _validation_errors(normalized)
    reason = ""
    forced_clarify = False

    if parse_error:
        reason = f"parse_error:{parse_error}"
        forced_clarify = True
    elif errors:
        reason = f"schema_error:{errors[0]}"
        forced_clarify = True

    kind = str(normalized.get("kind", "CLARIFY"))
    sources = normalized.get("sources")
    if not isinstance(sources, list):
        sources = []
    normalized["sources"] = [item for item in sources if isinstance(item, dict)]

    if kind == "CLARIFY":
        needs = normalized.get("needs")
        if not isinstance(needs, dict):
            needs = {"type": "meaning", "options": []}
        needs_type = str(needs.get("type", "meaning"))
        if needs_type not in NEEDS_TYPES:
            needs_type = "meaning"
        options = needs.get("options")
        if not isinstance(options, list):
            options = []
        normalized["needs"] = {
            "type": needs_type,
            "options": [str(item) for item in options if str(item).strip()][:5],
        }
        normalized["text"] = _single_question(str(normalized.get("text", "")))
        normalized["task_plan"] = None
    elif kind == "TASK_PLAN":
        task_plan = normalized.get("task_plan")
        steps = task_plan.get("steps") if isinstance(task_plan, dict) else None
        if not isinstance(steps, list) or len(steps) < 1 or len(steps) > 3:
            reason = "task_plan_invalid_steps"
            forced_clarify = True
    elif kind == "ANSWER":
        if len(normalized["sources"]) == 0:
            reason = "answer_without_sources"
            forced_clarify = True
        normalized["needs"] = None
        normalized["task_plan"] = None
    else:
        reason = "kind_not_allowed"
        forced_clarify = True

    evidence_scope = _evidence_scope(normalized["sources"])
    if str(normalized.get("kind")) == "ANSWER" and evidence_scope == "none":
        reason = "answer_without_evidence_scope"
        forced_clarify = True

    if forced_clarify:
        fallback_options: list[str] = []
        user_rules = ctx.get("user_rules", [])
        if isinstance(user_rules, list):
            for row in user_rules[:3]:
                if isinstance(row, dict) and row.get("key"):
                    fallback_options.append(str(row["key"]))
        normalized = make_clarify_contract(
            text="질문의 핵심 의도를 한 문장으로 설명해주실 수 있을까요?",
            needs_type="meaning",
            options=fallback_options,
            confidence_model=float(normalized.get("confidence_model", 0.0) or 0.0),
        )
        evidence_scope = _evidence_scope(normalized["sources"])

    confidence_model = float(normalized.get("confidence_model", 0.0) or 0.0)
    score = 0.2
    if normalized["kind"] != "CLARIFY":
        score += 0.2
    if evidence_scope != "none":
        score += 0.3
    score += _clamp(confidence_model) * 0.3

    gate = {
        "pass": True,
        "reason": reason,
        "gate_score": round(_clamp(score), 4),
        "evidence_scope": evidence_scope,
        "schema_errors": errors,
        "fallback_applied": forced_clarify,
    }
    return normalized, gate


def parse_validate_and_gate(
    raw: str,
    *,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = parse_contract_json(raw)
    if parsed is None:
        return validate_and_gate_contract({}, context=context, parse_error="json_parse_failed")
    return validate_and_gate_contract(parsed, context=context)
