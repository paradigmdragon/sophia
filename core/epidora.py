import re
from typing import List, Optional
from pydantic import BaseModel
from .schema import PatchOption

class EpidoraSignal(BaseModel):
    code: str
    detected_at: int # offset
    snippet: str
    message: str # Gap question
    options: List[PatchOption]

class EpidoraEngine:
    def __init__(self):
        self.patterns = {
            "EPI-00": {
                "regex": r"(안녕|반가워|시작|Sophia|소피아)",
                "message": "안녕하세요, 무엇을 도와드릴까요?",
                "options": [
                    PatchOption(id="opt_1", semantic="greeting", label="인사")
                ]
            },
            "EPI-01": {
                "regex": r"((정의|뜻|의미).*(뭐|무엇|인가|뭔|어떤|무슨)|(뭐|무엇|인가|뭔|어떤|무슨).*(정의|뜻|의미))",
                "message": "이 단어는 이 상황에서 어떤 특별한 의미를 갖나요?",
                "options": [
                    PatchOption(id="opt_1", semantic="define_context", label="맥락적 정의 추가"),
                    PatchOption(id="opt_2", semantic="keep_ambiguous", label="모호함 유지")
                ]
            },
            "EPI-02": {
                "regex": r"(느껴진다|같다|보인다)",
                "message": "이 부분은 직접 느끼신 것인가요, 아니면 보신 것인가요?",
                "options": [
                    PatchOption(id="opt_1", semantic="first_person", label="1인칭 경험으로 서술"),
                    PatchOption(id="opt_2", semantic="third_person", label="3인칭 관찰로 서술")
                ]
            },
            "EPI-03": {
                "regex": r"(항상|절대|무조건|법칙)",
                "message": "이 경험이 주인님에게는 하나의 법칙처럼 느껴지시나요?",
                "options": [
                    PatchOption(id="opt_1", semantic="make_rule", label="나만의 원칙으로 정립"),
                    PatchOption(id="opt_2", semantic="one_time_event", label="일회성 사건으로 기록")
                ]
            },
            "EPI-04": {
                "regex": r"(결과|갑자기|변했다|되었다)",
                "message": "그 상태가 되기까지 어떤 마음의 변화가 있었나요?",
                "options": [
                    PatchOption(id="opt_1", semantic="describe_process", label="과정 서술 추가"),
                    PatchOption(id="opt_2", semantic="focus_result", label="결과에 집중")
                ]
            },
            "EPI-05": {
                "regex": r"(이상하다|다르다|충돌|모순)",
                "message": "이 새로운 경험은 기존의 생각과 어떻게 어우러질 수 있을까요?",
                "options": [
                    PatchOption(id="opt_1", semantic="expand_frame", label="기존 생각 확장"),
                    PatchOption(id="opt_2", semantic="new_category", label="새로운 범주 생성")
                ]
            },
            "EPI-06": {
                "regex": r"(알 수 있다|생각된다|판단된다)", # Passive voice or missing subject
                "message": "이 생각은 주인님의 마음에서 나온 것인가요?",
                "options": [
                    PatchOption(id="opt_1", semantic="add_subject", label="주어(나) 명시"),
                    PatchOption(id="opt_2", semantic="keep_objective", label="객관적 서술 유지")
                ]
            }
        }

    def detect(self, text: str) -> List[EpidoraSignal]:
        """
        Analyzes text for structural alignment opportunities.
        Returns a list of signals (gaps).
        """
        signals = []
        for code, pattern in self.patterns.items():
            match = re.search(pattern["regex"], text)
            if match:
                signals.append(EpidoraSignal(
                    code=code,
                    detected_at=match.start(),
                    snippet=match.group(),
                    message=pattern["message"],
                    options=pattern["options"]
                ))
        return signals
