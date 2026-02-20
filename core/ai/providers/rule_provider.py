from __future__ import annotations

import re
from collections import Counter

from core.ai.providers.base import BaseProvider, ProviderResult


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_:-]+")


def _top_tokens(text: str, *, limit: int = 5) -> list[str]:
    words = [item.lower() for item in _TOKEN_RE.findall(text or "") if len(item) >= 2]
    counts = Counter(words)
    return [token for token, _ in counts.most_common(limit)]


class RuleProvider(BaseProvider):
    name = "rule"

    def run(self, task: str, payload: dict) -> ProviderResult:
        text = str(payload.get("text", "") or "")
        hint = str(payload.get("context_tag_hint", "") or "").strip().lower()
        tags = _top_tokens(text, limit=5)

        if task == "ingest":
            context_tag = hint if hint in {"chat", "work", "diary", "doc", "legal"} else "chat"
            data = {
                "schema": "ingest_contract.v0.1",
                "summary_120": " ".join(text.split())[:120] or "unknown",
                "entities": [],
                "tags": tags,
                "context_tag": context_tag,
                "confidence_model": 0.55,
            }
            return ProviderResult(provider=self.name, ok=True, data=data)

        if task == "transcript":
            has_question = "?" in text or "질문" in text
            data = {
                "schema": "transcript_contract.v0.1",
                "summary": " ".join(text.split())[:220] or "unknown",
                "action_items": [],
                "decisions": [],
                "open_questions": (
                    [{"q": "핵심 범위를 다시 정의할까요?", "type": "scope"}] if has_question else []
                ),
            }
            return ProviderResult(provider=self.name, ok=True, data=data)

        if task == "rules":
            candidates = []
            for token in tags[:3]:
                candidates.append(
                    {
                        "type": "preference",
                        "key": token,
                        "value": "unknown",
                        "evidence_refs": [str(item) for item in payload.get("refs", [])[:3]],
                        "confidence_model": 0.35,
                    }
                )
            data = {
                "schema": "rule_candidate.v0.1",
                "candidates": candidates,
            }
            return ProviderResult(provider=self.name, ok=True, data=data)

        if task == "diff":
            before = str(payload.get("before_text", "") or "")
            after = str(payload.get("after_text", "") or "")
            changed = before.strip() != after.strip()
            data = {
                "schema": "diff_contract.v0.1",
                "diff_summary": "내용 변경 감지" if changed else "실질 변경 없음",
                "changed_principles": (
                    [{"from": "unknown", "to": "unknown"}] if changed and (before or after) else []
                ),
                "affected_modules": _top_tokens(after, limit=3),
                "clarify": [],
            }
            return ProviderResult(provider=self.name, ok=True, data=data)

        if task == "anchor":
            anchors = [{"term": token, "definition": "unknown", "relations": []} for token in tags[:3]]
            data = {
                "schema": "anchor_candidate.v0.1",
                "summary_120": " ".join(text.split())[:120] or "unknown",
                "anchors": anchors,
                "linked_bits": tags[:5],
            }
            return ProviderResult(provider=self.name, ok=True, data=data)

        return ProviderResult(provider=self.name, ok=False, error=f"unsupported task: {task}")
