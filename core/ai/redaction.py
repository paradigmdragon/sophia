from __future__ import annotations

import hashlib
import re
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"OPENAI_API_KEY", re.IGNORECASE),
    re.compile(r"AWS_SECRET", re.IGNORECASE),
    re.compile(r"PASSWORD\s*=", re.IGNORECASE),
    re.compile(r"TOKEN\s*=", re.IGNORECASE),
    # Sentinel-like or high-entropy token style: ABC_DEF_123..., >=12 chars.
    re.compile(r"\b[A-Z0-9_]{12,}\b"),
]


def sha256_text(value: str) -> str:
    payload = (value or "").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def _contains_secret(value: str) -> bool:
    for pattern in SECRET_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _redact_string(value: str) -> tuple[str, bool]:
    if _contains_secret(value):
        return "[REDACTED_SECRET_CONTENT]", True
    return value, False


def redact_data(value: Any, *, path: str = "$") -> tuple[Any, list[str]]:
    if isinstance(value, str):
        redacted, changed = _redact_string(value)
        return redacted, ([path] if changed else [])

    if isinstance(value, list):
        out: list[Any] = []
        fields: list[str] = []
        for idx, item in enumerate(value):
            item_redacted, item_fields = redact_data(item, path=f"{path}[{idx}]")
            out.append(item_redacted)
            fields.extend(item_fields)
        return out, fields

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        fields: list[str] = []
        for key, item in value.items():
            child_path = f"{path}.{key}"
            item_redacted, item_fields = redact_data(item, path=child_path)
            out[str(key)] = item_redacted
            fields.extend(item_fields)
        return out, fields

    return value, []
