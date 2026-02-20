from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnconsciousReply:
    category: str
    text: str
    kind: str = "ANSWER"


def _contains_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def classify_user_input(text: str) -> str:
    lowered = (text or "").strip().lower()
    if not lowered:
        return "smalltalk"

    if _contains_any(lowered, ["ping", "hello", "hi", "안녕", "테스트", "test"]):
        return "test"
    if _contains_any(lowered, ["뭐해", "뭐 하", "무슨 작업", "작업 없어", "대기열"]):
        return "status"
    if _contains_any(lowered, ["ㅋㅋ", "ㅎㅎ", "하하", "아…", "아..", "답답", "힘들", "짜증"]):
        return "emotion"
    if _contains_any(lowered, ["해줘", "해 줄", "진행", "실행", "분석", "작성"]):
        return "directive"
    return "smalltalk"


def generate_unconscious_reply(user_text: str, *, prefix: str) -> UnconsciousReply:
    category = classify_user_input(user_text)

    if category == "test":
        return UnconsciousReply(
            category=category,
            text=f"{prefix} 연결 상태는 정상입니다. 어떤 작업부터 진행할까요?",
        )

    if category == "status":
        return UnconsciousReply(
            category=category,
            text=f"{prefix} 작업 대기열은 0건입니다. 에디터 글 분석부터 시작할까요?",
        )

    if category == "emotion":
        return UnconsciousReply(
            category=category,
            text=f"{prefix} 지금 상태를 짧게 정리해 주시면 제가 단계별로 정리해 드릴게요.",
        )

    if category == "directive":
        return UnconsciousReply(
            category=category,
            text=f"{prefix} 요청을 받았어요. 우선순위 하나만 지정해 주실 수 있을까요?",
            kind="CLARIFY",
        )

    return UnconsciousReply(
        category=category,
        text=f"{prefix} 이어서 진행할 주제를 한 줄로 알려주시면 바로 맞춰서 도와드릴게요.",
    )
