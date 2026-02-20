from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable

from core.chat.chat_gate import parse_validate_and_gate
from sophia_kernel.modules.clarify_and_learn import build_clarify_question, detect_ambiguous_term
from sophia_kernel.modules.unconscious_reply import generate_unconscious_reply

MASTER_TITLE = "주인님"
BANNED_META_PHRASES = {
    "현재 맥락을 유지하고 있습니다",
    "무엇을 의미하게 할까요",
    "what would you like",
    "maintaining the current context",
}


@dataclass(frozen=True)
class PersonaStageProfile:
    stage: str
    prefix: str
    tone_note: str


PERSONA_STAGE_PROFILES: dict[str, PersonaStageProfile] = {
    "early": PersonaStageProfile(
        stage="early",
        prefix="네, 주인님.",
        tone_note="system_soft",
    ),
    "mid": PersonaStageProfile(
        stage="mid",
        prefix="네, 주인님!",
        tone_note="maid",
    ),
    "late": PersonaStageProfile(
        stage="late",
        prefix="분부대로, 주인님.",
        tone_note="butler",
    ),
}


# Growth route is intentionally open but conservative.
# Automatic stage promotion is disabled by default; it can be enabled later
# when enough longitudinal analysis data is available.
def resolve_persona_stage() -> PersonaStageProfile:
    configured = os.getenv("SOPHIA_PERSONA_STAGE", "early").strip().lower()
    return PERSONA_STAGE_PROFILES.get(configured, PERSONA_STAGE_PROFILES["early"])


def _contains_hangul(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


def _looks_english_dominant(text: str) -> bool:
    source = text or ""
    if _contains_hangul(source):
        return False
    letters = re.findall(r"[A-Za-z]", source)
    return len(letters) >= 8


def _is_ping_like(text: str) -> bool:
    lowered = (text or "").strip().lower()
    patterns = ["ping", "hello", "hi", "안녕", "연결"]
    return any(token in lowered for token in patterns)


def _is_smoke_like(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return "smoke" in lowered or "스모크" in lowered or "smoke test" in lowered


def _is_work_queue_like(text: str) -> bool:
    lowered = (text or "").strip().lower()
    patterns = ["지금 무슨 작업", "작업 없어", "작업있", "작업 있", "대기열", "queue"]
    return any(token in lowered for token in patterns)


def _fallback_bundle(user_text: str, stage: PersonaStageProfile) -> dict[str, Any]:
    unconscious = generate_unconscious_reply(user_text, prefix=stage.prefix)

    if _is_ping_like(user_text):
        text = unconscious.text
        return {
            "text": text,
            "kind": "ANSWER",
            "needs": None,
            "task_plan": None,
            "sources": [{"type": "rules", "ref": "fallback:ping"}],
            "confidence_model": 0.4,
            "fallback_reason": "ping_like",
        }

    if _is_smoke_like(user_text):
        text = (
            f"{stage.prefix} 스모크 테스트는 이미 통과했습니다. "
            "다음으로 데스크탑 앱에서 실제 채팅과 노트 자동 생성 흐름을 점검하면 됩니다."
        )
        return {
            "text": text,
            "kind": "ANSWER",
            "needs": None,
            "task_plan": None,
            "sources": [{"type": "rules", "ref": "fallback:smoke"}],
            "confidence_model": 0.45,
            "fallback_reason": "smoke_like",
        }

    if _is_work_queue_like(user_text):
        text = unconscious.text
        return {
            "text": text,
            "kind": "ANSWER",
            "needs": None,
            "task_plan": None,
            "sources": [{"type": "rules", "ref": "fallback:work_queue"}],
            "confidence_model": 0.45,
            "fallback_reason": "work_queue_like",
        }

    term = detect_ambiguous_term(user_text) or "작업"
    text = build_clarify_question(term)
    return {
        "text": text,
        "kind": "CLARIFY",
        "needs": {"type": "meaning", "options": ["대기열", "에디터 분석", "IDE 지시"]},
        "task_plan": None,
        "sources": [{"type": "rules", "ref": "fallback:unknown"}],
        "confidence_model": 0.35,
        "fallback_reason": "unknown_intent",
    }


def _memory_lookup(context: dict[str, Any]) -> dict[str, Any]:
    raw = context.get("memory_lookup") if isinstance(context, dict) else None
    if not isinstance(raw, dict):
        return {"memory_hits": [], "memory_notes": [], "tone_hint": "", "memory_used": False}
    return {
        "memory_hits": list(raw.get("memory_hits", [])),
        "memory_notes": list(raw.get("memory_notes", [])),
        "tone_hint": str(raw.get("tone_hint", "")),
        "memory_used": bool(raw.get("memory_used", False)),
    }


def _apply_tone_hint(text: str, tone_hint: str) -> str:
    clean = " ".join((text or "").split()).strip()
    hint = (tone_hint or "").lower()
    if not clean or not hint:
        return clean

    if "짧" in hint:
        chunks = re.split(r"(?<=[.!?])\s+", clean)
        return chunks[0].strip() if chunks and chunks[0].strip() else clean
    if any(token in hint for token in ["부드", "차분", "정중"]):
        if "부드럽게" not in clean:
            return f"{clean} 차분하게 이어가겠습니다."
    return clean


def _compose_reply_with_memory(
    *,
    text: str,
    stage: PersonaStageProfile,
    context: dict[str, Any],
) -> tuple[str, list[str], bool]:
    memory = _memory_lookup(context)
    hits = [str(item).strip() for item in memory.get("memory_hits", []) if str(item).strip()][:5]
    notes = [str(item).strip() for item in memory.get("memory_notes", []) if str(item).strip()]
    tone_hint = str(memory.get("tone_hint", "")).strip()

    composed = _apply_tone_hint(text, tone_hint)
    memory_used = False

    if notes:
        memory_line = notes[0]
        stripped = composed.strip()
        if stripped.startswith(stage.prefix):
            stripped = stripped[len(stage.prefix) :].strip()
        composed = f"{stage.prefix} {memory_line}"
        if stripped:
            composed = f"{composed} {stripped}"
        memory_used = True
    elif tone_hint:
        memory_used = True

    return composed.strip(), hits, memory_used


def _normalize_korean_reply(text: str, stage: PersonaStageProfile) -> str:
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return f"{stage.prefix} 어떤 작업부터 시작하면 좋을까요?"

    lowered = clean.lower()
    if any(phrase in lowered for phrase in BANNED_META_PHRASES):
        return ""

    # Greeting-only responses are not allowed.
    if re.fullmatch(r"(네[, ]*)?주인님[.!]?", clean):
        return f"{stage.prefix} 요청하신 내용을 한 줄로 알려주시면 바로 이어서 처리하겠습니다."

    if MASTER_TITLE not in clean:
        clean = f"{stage.prefix} {clean}".strip()

    # Force Korean fallback if response is mostly English.
    if _looks_english_dominant(clean):
        return ""

    return clean


def generate_chat_reply(
    *,
    user_text: str,
    context: dict[str, Any],
    llm_call: Callable[[str, dict[str, Any]], str],
) -> dict[str, Any]:
    stage = resolve_persona_stage()
    memory = _memory_lookup(context)
    raw = ""
    try:
        raw = (llm_call(user_text, context) or "").strip()
    except Exception:
        raw = ""

    contract, gate = parse_validate_and_gate(raw, context=context)
    kind = str(contract.get("kind", "CLARIFY")).upper()
    text = str(contract.get("text", "")).strip()

    fallback_required = False
    fallback_reason = ""

    if not raw:
        fallback_required = True
        fallback_reason = "llm_unavailable"
    elif bool(gate.get("fallback_applied", False)):
        fallback_required = True
        fallback_reason = str(gate.get("reason", "contract_fallback")) or "contract_fallback"

    normalized = _normalize_korean_reply(text, stage)
    if not normalized:
        fallback_required = True
        if not fallback_reason:
            fallback_reason = "text_quality"

    if fallback_required:
        bundle = _fallback_bundle(user_text, stage)
        composed_text, memory_hits, memory_used = _compose_reply_with_memory(
            text=str(bundle.get("text", "")),
            stage=stage,
            context=context,
        )
        normalized = _normalize_korean_reply(composed_text, stage) or composed_text
        return {
            **bundle,
            "text": normalized,
            "gate": gate,
            "fallback_applied": True,
            "persona_stage": stage.stage,
            "call_user": MASTER_TITLE,
            "memory_hits": memory_hits,
            "memory_used": bool(memory_used and memory.get("memory_used", False) and memory_hits),
        }

    composed_text, memory_hits, memory_used = _compose_reply_with_memory(
        text=normalized,
        stage=stage,
        context=context,
    )
    normalized = _normalize_korean_reply(composed_text, stage) or normalized
    return {
        "text": normalized,
        "kind": kind,
        "needs": contract.get("needs"),
        "task_plan": contract.get("task_plan"),
        "sources": contract.get("sources") if isinstance(contract.get("sources"), list) else [],
        "confidence_model": float(contract.get("confidence_model", 0.0) or 0.0),
        "gate": gate,
        "fallback_applied": False,
        "fallback_reason": "",
        "persona_stage": stage.stage,
        "call_user": MASTER_TITLE,
        "memory_hits": memory_hits,
        "memory_used": bool(memory_used and memory.get("memory_used", False) and memory_hits),
    }
