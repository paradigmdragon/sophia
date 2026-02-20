from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


@lru_cache(maxsize=1)
def _load_templates() -> dict[str, Any]:
    def _read_json(name: str) -> dict[str, Any]:
        path = TEMPLATE_DIR / name
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
        if isinstance(value, dict):
            return value
        return {}

    return {
        "tone": _read_json("tone.json"),
        "intent": _read_json("intent.json"),
        "notice": _read_json("notice.json"),
        "question": _read_json("question.json"),
    }


def classify_intent(text: str) -> str:
    content = (text or "").strip().lower()
    if not content:
        return "general"

    if any(token in content for token in ["보류", "잠시", "대기", "hold", "later"]):
        return "hold"
    if any(token in content for token in ["아니", "취소", "거절", "no ", "don't", "중지"]):
        return "reject"
    if any(token in content for token in ["?", "왜", "어떻게", "무엇", "what", "how", "can you", "could you"]):
        return "question"
    if any(token in content for token in ["해줘", "해주세요", "해라", "do ", "run ", "create ", "implement", "작성", "진행"]):
        return "directive"
    if any(token in content for token in ["네", "승인", "좋아", "yes", "ok", "확인"]):
        return "approve"
    return "general"


def _pick_by_seed(options: list[str], seed_text: str) -> str:
    if not options:
        return ""
    if len(options) == 1:
        return options[0]
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(options)
    return options[idx]


def _safe_format(template: str, slots: dict[str, Any] | None = None) -> str:
    if not slots:
        return template
    safe_slots = {str(k): str(v) for k, v in slots.items()}
    out = template
    for key, value in safe_slots.items():
        out = out.replace("{" + key + "}", value)
    return out


def _apply_tone(content: str, tone_key: str = "neutral") -> str:
    templates = _load_templates()
    tone_doc = templates.get("tone", {})
    tones = tone_doc.get("tones", {}) if isinstance(tone_doc, dict) else {}
    tone = tones.get(tone_key, tones.get("neutral", {})) if isinstance(tones, dict) else {}
    prefix = str(tone.get("prefix", "")) if isinstance(tone, dict) else ""
    suffix = str(tone.get("suffix", "")) if isinstance(tone, dict) else ""
    return f"{prefix}{content}{suffix}".strip()


def build_intent_reply(intent: str, seed_text: str, *, tone: str = "neutral", slots: dict[str, Any] | None = None) -> str:
    templates = _load_templates()
    intent_doc = templates.get("intent", {})
    notice_doc = templates.get("notice", {})

    keys = intent_doc.get(intent) if isinstance(intent_doc, dict) else None
    if not isinstance(keys, list) or not keys:
        keys = intent_doc.get("general", ["intent.general.a"]) if isinstance(intent_doc, dict) else ["intent.general.a"]
    template_key = _pick_by_seed([str(k) for k in keys], seed_text)
    template = notice_doc.get(template_key, notice_doc.get("intent.general.a", "네 주인님."))
    return _apply_tone(_safe_format(str(template), slots), tone_key=tone)


def build_notice(key: str, *, tone: str = "neutral", slots: dict[str, Any] | None = None) -> str:
    templates = _load_templates()
    notice_doc = templates.get("notice", {})
    template = notice_doc.get(key, key) if isinstance(notice_doc, dict) else key
    return _apply_tone(_safe_format(str(template), slots), tone_key=tone)


def build_question_prompt(cluster_id: str, *, tone: str = "neutral") -> str:
    templates = _load_templates()
    question_doc = templates.get("question", {})
    lines = question_doc.get(cluster_id) if isinstance(question_doc, dict) else None
    if not isinstance(lines, list) or not lines:
        lines = question_doc.get("default", ["주인님, 반복되는 의심 신호가 감지되었습니다."]) if isinstance(question_doc, dict) else [
            "주인님, 반복되는 의심 신호가 감지되었습니다."
        ]
    content = "\n".join(str(line) for line in lines if str(line).strip())
    return _apply_tone(content, tone_key=tone)
