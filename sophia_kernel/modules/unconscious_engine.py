from __future__ import annotations

import re
from typing import Any


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def classify_unconscious_intent(text: str, history_digest: str) -> dict[str, Any] | None:
    lowered = (text or "").strip().lower()
    digest = (history_digest or "").strip().lower()
    if not lowered:
        return {
            "pattern_id": "UNKNOWN_BUT_ACTIONABLE",
            "confidence": 0.45,
            "params": {"hint": "작업"},
        }

    if _contains_any(lowered, ["ping", "health check", "헬스체크", "연결 확인"]):
        return {"pattern_id": "PING_OK", "confidence": 0.95, "params": {}}

    if _contains_any(lowered, ["smoke", "스모크", "smoke test"]):
        return {"pattern_id": "SMOKE_OK", "confidence": 0.92, "params": {}}

    if _contains_any(lowered, ["안녕", "하이", "hello", "hi", "반가", "좋은 아침"]):
        return {"pattern_id": "GREET", "confidence": 0.8, "params": {}}

    if _contains_any(lowered, ["답답", "짜증", "망했", "힘들", "아..", "아…", "멘붕", "지쳤"]):
        return {"pattern_id": "EMOTION_VENT", "confidence": 0.78, "params": {}}

    if _contains_any(lowered, ["무슨 작업", "작업 있", "작업 없어", "대기열", "진행 상황", "work status"]):
        return {"pattern_id": "WORK_STATUS_QUERY", "confidence": 0.88, "params": {}}

    # Keep explicit planning/implementation requests on the main chat engine path.
    if _contains_any(lowered, ["계획", "task plan", "plan", "세워", "등록", "구성", "단계"]):
        return None

    vague_short = len(lowered) <= 12 and len(re.findall(r"[0-9A-Za-z가-힣]+", lowered)) <= 3
    if vague_short or _contains_any(lowered, ["이거", "그거", "이건", "이거 뭐"]):
        hint = "작업"
        for token in ["작업", "노트", "대기열", "분석", "ide", "에디터"]:
            if token in lowered:
                hint = token
                break
        if hint == "작업" and "대기열" in digest:
            hint = "대기열"
        return {
            "pattern_id": "UNKNOWN_BUT_ACTIONABLE",
            "confidence": 0.52,
            "params": {"hint": hint},
        }

    return None


def render_unconscious_reply(pattern_id: str, params: dict[str, Any], persona_level: int = 0) -> str:
    # Growth route is open, but v0 ships level 0 only.
    _ = persona_level
    prefix = "네, 주인님."

    if pattern_id == "PING_OK":
        return f"{prefix} 연결 상태는 정상입니다. 바로 진행할 작업을 말씀해 주세요."

    if pattern_id == "SMOKE_OK":
        return f"{prefix} 스모크 테스트 상태는 정상입니다. 다음 확인 항목 하나만 지정해 주세요."

    if pattern_id == "GREET":
        return f"{prefix} 준비되어 있습니다. 이어서 다룰 주제를 알려주세요."

    if pattern_id == "EMOTION_VENT":
        return f"{prefix} 지금 막히는 지점을 한 줄로 적어주시면 제가 순서대로 정리하겠습니다."

    if pattern_id == "WORK_STATUS_QUERY":
        ready_count = int(params.get("ready_count", 0) or 0)
        in_progress_count = int(params.get("in_progress_count", 0) or 0)
        recent_title = str(params.get("recent_work_title", "") or "").strip()
        notes_status = str(params.get("notes_status", "기록 없음") or "기록 없음").strip()
        recent_phrase = f"마지막 작업은 '{recent_title}'" if recent_title else "마지막 작업은 아직 없습니다"
        return (
            f"{prefix} 대기열 {ready_count}건, 진행 중 {in_progress_count}건이고 "
            f"{recent_phrase}, 노트 상태는 {notes_status}입니다."
        )

    hint = str(params.get("hint", "작업") or "작업").strip()
    return f"{prefix} 방금 말씀하신 '{hint}'은 대기열 확인 쪽일까요, 에디터 정리 쪽일까요?"
