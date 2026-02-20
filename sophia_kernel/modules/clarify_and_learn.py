from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.memory.schema import ChatTimelineMessage

AMBIGUOUS_TERMS = ["작업", "대기열", "노트", "ide"]
TOPIC_MIN_LEN = 2


@dataclass(frozen=True)
class LearningSignals:
    term_mapping: dict[str, Any] | None
    topic_seen: dict[str, Any] | None
    user_preference: dict[str, Any] | None


def build_clarify_question(term: str) -> str:
    clean = (term or "작업").strip()
    return (
        f"네, 주인님. 방금 말씀하신 ‘{clean}’은 대기열 점검, 에디터 분석, IDE 지시 중 어느 쪽인가요?"
    )


def detect_ambiguous_term(user_text: str) -> str | None:
    lowered = (user_text or "").strip().lower()
    for term in AMBIGUOUS_TERMS:
        if term in lowered:
            return term
    return None


def detect_user_preference(user_text: str) -> dict[str, Any] | None:
    text = (user_text or "").strip()
    lowered = text.lower()

    preference_patterns = [
        r"(말투|톤).*(좋아|선호)",
        r"나는 .*좋아",
        r"저는 .*선호",
    ]
    if not any(re.search(pattern, lowered) for pattern in preference_patterns):
        return None

    key = "response_tone"
    if "말투" in text:
        key = "response_tone"
    elif "속도" in text:
        key = "response_speed"

    return {
        "key": key,
        "value": text[:120],
        "confidence": 0.6,
    }


def _extract_topic_candidates(user_text: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣_:-]+", (user_text or "").lower())
    out: list[str] = []
    for token in tokens:
        if len(token) < TOPIC_MIN_LEN:
            continue
        if token in {"네", "주인님", "그리고", "합니다", "해요", "이다", "the", "and"}:
            continue
        if token not in out:
            out.append(token)
        if len(out) >= 8:
            break
    return out


def detect_topic_seen(session, *, context_tag: str, user_text: str, threshold: int = 3) -> dict[str, Any] | None:
    candidates = _extract_topic_candidates(user_text)
    if not candidates:
        return None

    rows = (
        session.query(ChatTimelineMessage)
        .filter(
            ChatTimelineMessage.role == "user",
            ChatTimelineMessage.context_tag == context_tag,
        )
        .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
        .limit(40)
        .all()
    )

    content_blob = "\n".join((row.content or "").lower() for row in rows)
    for candidate in candidates:
        count = content_blob.count(candidate)
        if count >= threshold:
            return {
                "topic": candidate,
                "count": count,
                "source": "chat",
            }
    return None


def collect_learning_signals(
    session,
    *,
    context_tag: str,
    user_text: str,
    learned_rule: dict[str, Any] | None,
) -> LearningSignals:
    term_mapping_payload: dict[str, Any] | None = None
    if learned_rule and learned_rule.get("key") and learned_rule.get("value"):
        term_mapping_payload = {
            "term": str(learned_rule.get("key")),
            "meaning": str(learned_rule.get("value")),
            "confidence": 0.7,
        }

    topic_seen_payload = detect_topic_seen(session, context_tag=context_tag, user_text=user_text)
    user_preference_payload = detect_user_preference(user_text)

    return LearningSignals(
        term_mapping=term_mapping_payload,
        topic_seen=topic_seen_payload,
        user_preference=user_preference_payload,
    )
