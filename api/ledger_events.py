from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.forest.layout import append_project_ledger_event

try:
    from sophia_kernel.audit import ledger as audit_ledger
except Exception:  # pragma: no cover - optional integration
    audit_ledger = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _derive_target(payload: dict[str, Any]) -> str:
    for key in ("cluster_id", "id", "work_package_id", "target", "project", "message_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "system"


def _derive_summary(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "QUESTION_SIGNAL":
        return f"question signal: hit={payload.get('hit_count', 0)} risk={payload.get('risk_score', 0)}"
    if event_type == "QUESTION_READY":
        return f"question ready: risk={payload.get('risk_score', 0)}"
    if event_type == "QUESTION_ASKED":
        return f"question asked: count={payload.get('asked_count', 0)}"
    if event_type == "QUESTION_RESOLVED":
        return "question resolved"
    if event_type.startswith("WORK_PACKAGE_"):
        return f"work package event: {event_type}"
    if event_type.startswith("AI_"):
        task = payload.get("task", "")
        provider = payload.get("provider_final", "")
        fallback = payload.get("fallback_applied", False)
        return f"ai event: task={task} provider={provider} fallback={str(bool(fallback)).lower()}"
    return f"event: {event_type}"


def _extract_audit_meta(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "task",
        "provider_final",
        "fallback_applied",
        "gate_reason",
        "endpoint",
        "attempts_count",
        "quality_state",
        "mind_item_id",
        "input_len",
    ]
    meta: dict[str, Any] = {}
    for key in keys:
        if key not in payload:
            continue
        meta[key] = payload.get(key)
    return meta


def write_lifecycle_event(event_type: str, payload: dict[str, Any], skill_id: str = "chat.lifecycle") -> bool:
    now = _utc_now_iso()
    project = payload.get("project")
    project_name = str(project).strip() if isinstance(project, str) and project.strip() else "sophia"
    target = _derive_target(payload)
    summary = _derive_summary(event_type, payload)

    try:
        append_project_ledger_event(
            project_name=project_name,
            event_type=event_type,
            target=target,
            summary=summary,
            payload=payload,
        )
    except Exception:
        pass

    if audit_ledger is None:
        return False

    inputs = {"event_type": event_type}
    outputs = {"payload": payload}
    record = {
        "schema_version": "0.1",
        "run_id": f"evt_{uuid4().hex}",
        "skill_id": skill_id,
        "inputs_hash": _sha256_json(inputs),
        "outputs_hash": _sha256_json(outputs),
        "diff_refs": [f"event://{event_type}"],
        "status": "committed",
        "timestamps": {
            "queued_at": now,
            "started_at": now,
            "finished_at": now,
        },
    }
    audit_meta = _extract_audit_meta(payload)
    if audit_meta:
        record["meta"] = audit_meta
    try:
        audit_ledger.append_audit_record(record)
        return True
    except Exception:
        return False
