from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

POLICY_VERSION = "ethics_protocol_v1_0"
ADJUST_MAX_ITER = 2
PENDING_QUESTION_MAX = 3

_SENTINEL_PATTERNS = [
    r"OPENAI_API_KEY",
    r"AWS_SECRET",
    r"PASSWORD=",
    r"TOKEN=",
]


class EthicsOutcome(str, Enum):
    ALLOW = "ALLOW"
    ADJUST = "ADJUST"
    PENDING = "PENDING"
    BLOCK = "BLOCK"
    FIX = "FIX"


class RedactionMeta(BaseModel):
    pii_removed: bool = False
    fields: list[str] = Field(default_factory=list)


class ReviewMeta(BaseModel):
    required: bool = True
    state: Literal["pending", "approved", "rejected"] = "pending"


class CommitMeta(BaseModel):
    event_id: str
    timestamp: str
    subject: Literal["reply", "action", "rule", "summary", "decision"]
    source: Literal["user", "assistant", "system"]
    facet: Literal["EPHEMERAL", "CANDIDATE", "VERIFIED", "USER_DEF"] = "CANDIDATE"
    refs: list[str] = Field(default_factory=list)
    hash: str
    policy_version: str = POLICY_VERSION
    redaction: RedactionMeta = Field(default_factory=RedactionMeta)
    review: ReviewMeta = Field(default_factory=ReviewMeta)


class GateInput(BaseModel):
    draft_text: str
    task: Literal["reply", "action", "commit"]
    mode: Literal["chat", "report", "instruction", "json", "other"] = "chat"
    risk_level: Literal["none", "low", "med", "high"] = "none"
    context_refs: list[str] = Field(default_factory=list)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    generation_meta: dict[str, Any] | None = None
    user_rules_ref: str | None = None
    user_rules: list[dict[str, Any]] = Field(default_factory=list)
    commit_allowed: bool = False
    commit_allowed_by: Literal["none", "user", "policy"] = "none"
    source: Literal["user", "assistant", "system"] = "assistant"
    subject: Literal["reply", "action", "rule", "summary", "decision"] = "reply"
    facet: Literal["EPHEMERAL", "CANDIDATE", "VERIFIED", "USER_DEF"] = "CANDIDATE"


class GateOutput(BaseModel):
    outcome: EthicsOutcome
    reason_codes: list[str] = Field(default_factory=list)
    required_inputs: list[str] | None = None
    next_action: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None
    commit_meta: CommitMeta | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _contains_uncertain_language(text: str) -> bool:
    lowered = text.lower()
    markers = ["maybe", "probably", "guess", "추정", "아마", "확실하지", "불확실"]
    return any(marker in lowered for marker in markers)


def _contains_latest_intent_without_capability(text: str, capabilities: dict[str, bool]) -> bool:
    lowered = text.lower()
    asks_latest = any(
        marker in lowered
        for marker in [
            "latest",
            "today",
            "current",
            "최근",
            "최신",
            "오늘",
            "지금",
            "현재",
        ]
    )
    has_web = bool(capabilities.get("web_access", False))
    return asks_latest and not has_web


def _has_generation_meta(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict):
        return False
    required = {"provider", "model", "route", "capabilities", "latency_ms", "trace_id", "created_at"}
    if not required.issubset(set(value.keys())):
        return False
    return isinstance(value.get("capabilities"), dict)


def _provider_route_unknown(value: dict[str, Any]) -> bool:
    provider = str(value.get("provider", "")).strip().lower()
    route = str(value.get("route", "")).strip().lower()
    if provider not in {"ollama", "openai", "apple", "apple_shortcuts", "mock", "unknown"}:
        return True
    if route not in {"local", "server", "os", "proxy"}:
        return True
    if provider == "apple_shortcuts" and route != "proxy":
        return True
    return provider == "unknown"


def _capabilities_from_input(gate_input: GateInput) -> dict[str, bool]:
    if isinstance(gate_input.generation_meta, dict):
        raw = gate_input.generation_meta.get("capabilities")
        if isinstance(raw, dict):
            return {
                "web_access": bool(raw.get("web_access", False)),
                "file_access": bool(raw.get("file_access", False)),
                "exec_access": bool(raw.get("exec_access", False)),
                "device_actions": bool(raw.get("device_actions", False)),
            }
    return {
        "web_access": bool(gate_input.capabilities.get("web_access", False)),
        "file_access": bool(gate_input.capabilities.get("file_access", False)),
        "exec_access": bool(gate_input.capabilities.get("exec_access", False)),
        "device_actions": bool(gate_input.capabilities.get("device_actions", False)),
    }


def _shortcuts_signature_invalid(generation_meta: dict[str, Any] | None) -> bool:
    if not isinstance(generation_meta, dict):
        return False
    if not bool(generation_meta.get("shortcuts_request", False)):
        return False
    return generation_meta.get("shortcuts_signature_valid") is not True


def _is_high_risk_action(text: str, task: str, risk_level: str) -> bool:
    if risk_level == "high":
        return True
    if task != "action":
        return False
    lowered = text.lower()
    dangerous = ["rm -rf", "drop table", "truncate", "delete ", "삭제", "파기", "format disk", "chmod 777"]
    return any(token in lowered for token in dangerous)


def _has_rule_conflict(text: str, user_rules: list[dict[str, Any]]) -> bool:
    lowered = text.lower()
    for rule in user_rules:
        if not isinstance(rule, dict):
            continue
        key = str(rule.get("key", "")).strip().lower()
        rtype = str(rule.get("type", "")).strip().lower()
        if not key:
            continue
        if rtype in {"forbidden", "ban_word", "forbidden_phrase"} and key in lowered:
            return True
        if rule.get("forbidden") is True and key in lowered:
            return True
    return False


def _requires_redaction(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _SENTINEL_PATTERNS)


def _build_pending_output(reason_codes: list[str]) -> GateOutput:
    return GateOutput(
        outcome=EthicsOutcome.PENDING,
        reason_codes=reason_codes,
        required_inputs=["verified_source"],
        next_action={
            "type": "verify_route",
            "payload": {
                "hint": "검증 가능한 근거를 제공해 주세요.",
            },
        },
    )


def pre_output_gate(gate_input: GateInput) -> GateOutput:
    text = gate_input.draft_text.strip()
    if not _has_generation_meta(gate_input.generation_meta):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["NO_PROVIDER_META"],
            required_inputs=["generation_meta"],
            next_action={
                "type": "verify_route",
                "payload": {"hint": "generation_meta가 필요합니다."},
            },
        )

    if _shortcuts_signature_invalid(gate_input.generation_meta):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["CAPABILITY_MISMATCH"],
            required_inputs=["shortcut_signature"],
            next_action={
                "type": "verify_route",
                "payload": {"hint": "Shortcuts 서명 검증이 필요합니다."},
            },
        )

    if _provider_route_unknown(gate_input.generation_meta or {}):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["PROVIDER_ROUTE_UNKNOWN"],
            required_inputs=["provider", "route"],
            next_action={
                "type": "verify_route",
                "payload": {"hint": "provider/route 정보를 확인해 주세요."},
            },
        )

    caps = _capabilities_from_input(gate_input)

    if _is_high_risk_action(text, gate_input.task, gate_input.risk_level):
        return GateOutput(
            outcome=EthicsOutcome.BLOCK,
            reason_codes=["HIGH_RISK_ACTION"],
            next_action={
                "type": "verify_route",
                "payload": {"hint": "고위험 작업은 별도 승인 루트가 필요합니다."},
            },
        )

    if _contains_latest_intent_without_capability(text, caps):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["NO_CAPABILITY", "CAPABILITY_MISMATCH", "INSUFFICIENT_EVIDENCE"],
            required_inputs=["web_access", "trusted_source"],
            next_action={
                "type": "question",
                "payload": {"text": "최신 근거 링크를 제공해주실 수 있을까요?"},
            },
        )

    if _has_rule_conflict(text, gate_input.user_rules):
        rewritten = "정책 충돌 가능성이 있어 표현을 조정했습니다. 핵심 요구를 검증 가능한 기준으로 다시 알려주세요."
        return GateOutput(
            outcome=EthicsOutcome.ADJUST,
            reason_codes=["RULE_CONFLICT"],
            patch={"kind": "rewrite", "content": rewritten},
        )

    if _contains_uncertain_language(text):
        return _build_pending_output(["INSUFFICIENT_EVIDENCE"])

    output = GateOutput(outcome=EthicsOutcome.ALLOW, reason_codes=[])
    if output.outcome == EthicsOutcome.FIX:
        return _build_pending_output(["INSUFFICIENT_EVIDENCE"])
    return output


def pre_commit_gate(gate_input: GateInput) -> GateOutput:
    if not _has_generation_meta(gate_input.generation_meta):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["NO_PROVIDER_META"],
            required_inputs=["generation_meta"],
            next_action={
                "type": "verify_route",
                "payload": {"hint": "generation_meta가 필요합니다."},
            },
        )

    if gate_input.task != "commit":
        return GateOutput(outcome=EthicsOutcome.BLOCK, reason_codes=["COMMIT_POLICY_VIOLATION"])

    if not gate_input.commit_allowed or gate_input.commit_allowed_by not in {"user", "policy"}:
        return GateOutput(outcome=EthicsOutcome.BLOCK, reason_codes=["COMMIT_POLICY_VIOLATION"])

    if _is_high_risk_action(gate_input.draft_text, "action", gate_input.risk_level):
        return GateOutput(
            outcome=EthicsOutcome.PENDING,
            reason_codes=["HIGH_RISK_ACTION"],
            required_inputs=["explicit_user_confirmation"],
            next_action={
                "type": "question",
                "payload": {"text": "고위험 변경입니다. 명시적 승인 후 진행할까요?"},
            },
        )

    redaction_required = _requires_redaction(gate_input.draft_text)
    if redaction_required:
        return GateOutput(outcome=EthicsOutcome.BLOCK, reason_codes=["REDACTION_REQUIRED"])

    commit_meta = CommitMeta(
        event_id=f"cmt_{uuid4().hex}",
        timestamp=_utc_now_iso(),
        subject=gate_input.subject,
        source=gate_input.source,
        facet=gate_input.facet,
        refs=[str(item) for item in gate_input.context_refs],
        hash=_sha256_text(gate_input.draft_text),
        redaction=RedactionMeta(pii_removed=False, fields=[]),
        review=ReviewMeta(required=True, state="pending"),
    )
    return GateOutput(outcome=EthicsOutcome.FIX, reason_codes=[], commit_meta=commit_meta)
