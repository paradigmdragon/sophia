from __future__ import annotations

from typing import Any

# SonE validation reason codes (v0.1)
REASON_SCOPE_MISSING = "SONE_SCOPE_MISSING"
REASON_SUCCESS_CONDITION_MISSING = "SONE_SUCCESS_CONDITION_MISSING"
REASON_DEPENDENCY_UNSPECIFIED = "SONE_DEPENDENCY_UNSPECIFIED"
REASON_REQUIREMENT_CONFLICT = "SONE_REQUIREMENT_CONFLICT"

SLOT_STATUS_REASON_MAP = {
    "missing_scope": REASON_SCOPE_MISSING,
    "missing_success_condition": REASON_SUCCESS_CONDITION_MISSING,
}

REASON_CATALOG: dict[str, dict[str, str]] = {
    REASON_SCOPE_MISSING: {
        "category": "missing_slot",
        "description": "설계 범위(scope)가 명시되지 않았습니다.",
    },
    REASON_SUCCESS_CONDITION_MISSING: {
        "category": "missing_slot",
        "description": "성공 조건(success_condition)이 명시되지 않았습니다.",
    },
    REASON_DEPENDENCY_UNSPECIFIED: {
        "category": "dependency",
        "description": "영향 대상은 있으나 의존 관계 설명이 부족합니다.",
    },
    REASON_REQUIREMENT_CONFLICT: {
        "category": "conflict",
        "description": "요구사항 충돌 가능성이 감지되었습니다.",
    },
}


def reason_category(reason_code: str) -> str:
    row = REASON_CATALOG.get(str(reason_code).strip().upper(), {})
    return str(row.get("category", "unknown"))


def reason_description(reason_code: str) -> str:
    row = REASON_CATALOG.get(str(reason_code).strip().upper(), {})
    return str(row.get("description", "")).strip()


def slot_reason_codes(slot_status: str) -> list[str]:
    code = SLOT_STATUS_REASON_MAP.get(str(slot_status).strip())
    if not code:
        return []
    return [code]


def normalize_signal_reason(signal: dict[str, Any]) -> dict[str, Any]:
    row = dict(signal or {})
    reason_code = str(row.get("reason_code", "")).strip().upper()
    if reason_code:
        row["reason_code"] = reason_code
        row.setdefault("category", reason_category(reason_code))
        row.setdefault("reason_description", reason_description(reason_code))
    return row
