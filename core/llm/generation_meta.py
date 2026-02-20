from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

_PROVIDER_MAP = {
    "ollama": "ollama",
    "openai": "openai",
    "apple": "apple",
    "apple_shortcuts": "apple_shortcuts",
    "foundation": "apple",
    "mock": "mock",
    "rule": "mock",
}

_ROUTE_BY_PROVIDER = {
    "ollama": "local",
    "openai": "server",
    "apple": "os",
    "apple_shortcuts": "proxy",
    "mock": "local",
    "unknown": "local",
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_provider(value: Any) -> str:
    key = str(value or "").strip().lower()
    return _PROVIDER_MAP.get(key, "unknown")


def _normalize_route(value: Any, provider: str) -> str:
    key = str(value or "").strip().lower()
    if key in {"local", "server", "os", "proxy"}:
        return key
    return _ROUTE_BY_PROVIDER.get(provider, "local")


def _normalize_capabilities(ctx: dict[str, Any]) -> dict[str, bool]:
    raw = ctx.get("capabilities") if isinstance(ctx, dict) else None
    data = raw if isinstance(raw, dict) else {}
    return {
        "web_access": bool(data.get("web_access", False)),
        "file_access": bool(data.get("file_access", False)),
        "exec_access": bool(data.get("exec_access", False)),
        "device_actions": bool(data.get("device_actions", False)),
    }


def _is_shortcuts_request(payload: dict[str, Any]) -> bool:
    user_agent = str(payload.get("user_agent") or "").strip().lower()
    headers = payload.get("headers")
    header_map = headers if isinstance(headers, dict) else {}
    source = str(header_map.get("x-sophia-source") or payload.get("source") or "").strip().lower()
    if source in {"shortcuts", "siri_shortcuts", "apple_shortcuts"}:
        return True
    return "shortcuts" in user_agent or "siri" in user_agent


def _normalize_shortcuts_status(value: Any) -> str:
    key = str(value or "").strip().upper()
    if key not in {"UNVERIFIED", "VERIFIED"}:
        return "UNVERIFIED"
    return key


def build_generation_meta(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(ctx or {})
    provider = _normalize_provider(payload.get("provider") or payload.get("provider_final") or payload.get("provider_primary"))
    route = _normalize_route(payload.get("route"), provider)
    shortcuts_status = _normalize_shortcuts_status(
        payload.get("shortcuts_status") or os.getenv("SOPHIA_SHORTCUTS_STATUS", "UNVERIFIED")
    )
    shortcuts_request = _is_shortcuts_request(payload)
    signature_valid_raw = payload.get("shortcuts_signature_valid")
    signature_valid = bool(signature_valid_raw) if isinstance(signature_valid_raw, bool) else False
    if shortcuts_request:
        if signature_valid:
            provider = "apple_shortcuts"
            route = "proxy"
        else:
            provider = "unknown"
            route = "proxy"

    latency_raw = payload.get("latency_ms", 0)
    try:
        latency_ms = int(latency_raw)
    except (TypeError, ValueError):
        latency_ms = 0

    def _token(value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    model = str(payload.get("model") or "unknown").strip() or "unknown"

    return {
        "provider": provider,
        "model": model,
        "route": route,
        "capabilities": _normalize_capabilities(payload),
        "latency_ms": max(0, latency_ms),
        "tokens_in": _token(payload.get("tokens_in")),
        "tokens_out": _token(payload.get("tokens_out")),
        "trace_id": str(payload.get("trace_id") or f"gen_{uuid4().hex}"),
        "created_at": str(payload.get("created_at") or _utc_now_iso()),
        "shortcuts_request": shortcuts_request,
        "shortcuts_signature_valid": signature_valid if shortcuts_request else None,
        "shortcuts_status": shortcuts_status,
        "integration": {"apple": {"shortcuts": shortcuts_status}},
    }


def attach_generation_meta(message_meta: dict[str, Any] | None, gen_meta: dict[str, Any]) -> dict[str, Any]:
    base = dict(message_meta or {})
    base["generation"] = dict(gen_meta)
    return base


def log_generation_line(gen_meta: dict[str, Any], *, logger: logging.Logger | None = None) -> None:
    logger_obj = logger or logging.getLogger(__name__)
    caps = gen_meta.get("capabilities", {}) if isinstance(gen_meta, dict) else {}
    logger_obj.info(
        "GEN provider=%s model=%s route=%s web=%s file=%s exec=%s latency_ms=%s trace_id=%s shortcuts_status=%s",
        str(gen_meta.get("provider", "unknown")),
        str(gen_meta.get("model", "unknown")),
        str(gen_meta.get("route", "local")),
        str(bool(caps.get("web_access", False))).lower(),
        str(bool(caps.get("file_access", False))).lower(),
        str(bool(caps.get("exec_access", False))).lower(),
        int(gen_meta.get("latency_ms", 0) or 0),
        str(gen_meta.get("trace_id", "")),
        str(gen_meta.get("shortcuts_status", "UNVERIFIED")),
    )
