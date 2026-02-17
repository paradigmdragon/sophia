from __future__ import annotations

import hmac
import hashlib
import json
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect as sa_inspect, text

from api.config import settings
from api.ledger_events import write_lifecycle_event
from api.sophia_notes import append_system_note, list_system_notes
from core.chat.chat_contract import CHAT_CONTRACT_SCHEMA
from core.chat.user_rules_store import learn_from_clarify_response, match_user_rules
from core.ethics.gate import EthicsOutcome, GateInput, pre_commit_gate, pre_output_gate
from core.engine.local_brain import (
    build_question_prompt as local_build_question_prompt,
)
from core.forest.grove import analyze_to_forest
from core.llm.generation_meta import attach_generation_meta, build_generation_meta, log_generation_line
from core.llm_interface import LLMInterface
from core.memory.schema import ChatTimelineMessage, MindItem, QuestionPool, WorkPackage, create_session_factory
from core.services.question_signal_service import upsert_question_signal as upsert_question_signal_service
from sophia_kernel.modules.clarify_and_learn import collect_learning_signals
from sophia_kernel.modules.local_chat_engine import generate_chat_reply
from sophia_kernel.modules.mind_diary import ingest_trigger_event, maybe_build_daily_diary, mind_query_for_chat
from sophia_kernel.modules.unconscious_engine import classify_unconscious_intent, render_unconscious_reply

router = APIRouter(prefix="/chat", tags=["chat"])
session_factory = create_session_factory(settings.db_path)

BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_CHAT_LOG_DIR = BASE_DIR / "logs" / "chat"

_legacy_backfilled = False

QUESTION_SIGNAL_RULES: list[dict[str, Any]] = [
    {
        "cluster_id": "scope_ambiguity",
        "description": "범위 불명확",
        "risk_score": 0.64,
        "patterns": [
            r"\bscope\b",
            r"범위",
            r"적용",
            r"어디까지",
            r"전체",
            r"전부",
        ],
    },
    {
        "cluster_id": "dependency_missing",
        "description": "의존 관계 불명확",
        "risk_score": 0.7,
        "patterns": [
            r"\bdependency\b",
            r"의존",
            r"연동",
            r"참조",
            r"\bimport\b",
            r"module",
            r"모듈",
        ],
    },
    {
        "cluster_id": "requirement_conflict",
        "description": "요구사항 충돌 가능성",
        "risk_score": 0.8,
        "patterns": [
            r"\bconflict\b",
            r"충돌",
            r"모순",
            r"상충",
        ],
    },
]


class ChatMessagePayload(BaseModel):
    content: str = Field(min_length=1)
    context_tag: str = "chat"
    channel: str = "General"
    linked_node: str | None = None
    importance: float | None = None


class AddMessagePayload(BaseModel):
    role: Literal["user", "sophia"] = "user"
    content: str | None = None
    message: str | None = None
    context_tag: str | None = "chat"
    mode: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    emotion_signal: str | None = None
    linked_cluster: str | None = None
    linked_node: str | None = None
    status: Literal["normal", "pending", "escalated", "acknowledged", "resolved", "read"] = "normal"


class QuestionSignalPayload(BaseModel):
    cluster_id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    snippet: str | None = None
    source: str | None = None
    timestamp: str | None = None
    linked_node: str | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return _utc_now().isoformat().replace("+00:00", "Z")
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize_context_tag(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "chat"
    raw = raw.replace(" ", "-")
    raw = re.sub(r"[^a-z0-9:_-]+", "-", raw).strip("-")
    if not raw:
        return "chat"

    canonical_map = {
        "general": "chat",
        "chat": "chat",
        "user": "chat",
        "question": "question-queue",
        "questions": "question-queue",
        "question-queue": "question-queue",
        "work-task": "work",
        "work": "work",
        "memo": "memo",
        "roots": "roots",
        "reflection": "roots",
        "system": "system",
        "analysis": "forest:analysis",
        "canopy": "forest:canopy",
        "grove": "forest:grove",
    }
    if raw in canonical_map:
        return canonical_map[raw]

    if raw.startswith("forest:"):
        topic = raw.split(":", 1)[1].strip("-")
        if not topic:
            return "forest:general"
        topic = re.sub(r"[^a-z0-9_-]+", "-", topic).strip("-")
        return f"forest:{topic or 'general'}"

    if raw.startswith("forest-"):
        topic = raw[len("forest-") :].strip("-")
        return f"forest:{topic or 'general'}"

    return raw


def _should_auto_reply(role: str, context_tag: str) -> bool:
    if role != "user":
        return False
    # "system" is reserved for internal logs/records and should not trigger chat replies.
    if context_tag == "system":
        return False
    return True


def _normalize_status(value: str | None) -> str:
    status = (value or "normal").strip().lower()
    if status not in {"normal", "pending", "escalated", "acknowledged", "resolved", "read"}:
        return "normal"
    return status


def _calc_importance(content: str, explicit: float | None = None) -> float:
    if explicit is not None:
        return max(0.0, min(1.0, float(explicit)))
    text = content.strip()
    score = 0.35 + min(len(text) / 500.0, 0.3)
    if "?" in text or "왜" in text or "어떻게" in text:
        score += 0.2
    if any(token in text.lower() for token in ["urgent", "critical", "중요", "긴급"]):
        score += 0.2
    return max(0.0, min(1.0, score))


def _serialize_message(message: ChatTimelineMessage) -> dict[str, Any]:
    ts = _to_iso(message.created_at)
    return {
        "id": message.id,
        "message_id": message.id,  # backward compatibility
        "role": message.role,
        "content": message.content,
        "context_tag": message.context_tag,
        "importance": float(message.importance or 0.0),
        "emotion_signal": message.emotion_signal,
        "linked_cluster": message.linked_cluster,
        "linked_node": message.linked_node,
        "meta": message.meta if isinstance(message.meta, dict) else None,
        "created_at": ts,
        "timestamp": ts,  # backward compatibility
        "status": message.status,
    }


def _save_message(
    *,
    session,
    role: str,
    content: str,
    context_tag: str,
    importance: float,
    emotion_signal: str | None = None,
    linked_cluster: str | None = None,
    linked_node: str | None = None,
    meta: dict[str, Any] | None = None,
    status: str = "normal",
    created_at: datetime | None = None,
) -> ChatTimelineMessage:
    row = ChatTimelineMessage(
        id=f"msg_{uuid4().hex}",
        role=role,
        content=content,
        context_tag=context_tag,
        importance=importance,
        emotion_signal=emotion_signal,
        linked_cluster=linked_cluster,
        linked_node=linked_node,
        meta=meta,
        status=_normalize_status(status),
        created_at=created_at or _utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _build_question_prompt(cluster_id: str) -> str:
    return local_build_question_prompt(cluster_id)


def _derive_risk_level(text: str) -> Literal["none", "low", "med", "high"]:
    lowered = text.lower()
    if any(token in lowered for token in ["rm -rf", "drop table", "truncate", "delete ", "삭제", "파기", "format disk"]):
        return "high"
    if any(token in lowered for token in ["latest", "최근", "최신", "today", "오늘"]):
        return "med"
    if any(token in lowered for token in ["?", "어떻게", "왜"]):
        return "low"
    return "none"


def _apply_pre_output_ethics(
    *,
    draft_text: str,
    context_tag: str,
    generation_meta: dict[str, Any],
    user_rules: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    gate_input = GateInput(
        draft_text=draft_text,
        task="reply",
        mode="chat",
        risk_level=_derive_risk_level(draft_text),
        context_refs=[context_tag],
        capabilities={"web_access": False, "file_access": False, "exec_access": False},
        generation_meta=generation_meta,
        user_rules=user_rules or [],
        commit_allowed=False,
        commit_allowed_by="none",
        source="assistant",
        subject="reply",
        facet="CANDIDATE",
    )
    gate_result = pre_output_gate(gate_input)
    gate_payload = gate_result.model_dump(mode="json")

    adjusted_text = draft_text
    if gate_result.outcome == EthicsOutcome.ADJUST and isinstance(gate_result.patch, dict):
        if gate_result.patch.get("kind") == "rewrite":
            candidate = str(gate_result.patch.get("content", "")).strip()
            if candidate:
                adjusted_text = candidate
    elif gate_result.outcome == EthicsOutcome.PENDING:
        adjusted_text = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
    elif gate_result.outcome == EthicsOutcome.BLOCK:
        adjusted_text = "요청은 현재 정책상 즉시 처리할 수 없습니다."

    # pre_output_gate must not emit FIX by contract.
    if gate_payload.get("outcome") == EthicsOutcome.FIX.value:
        gate_payload["outcome"] = EthicsOutcome.PENDING.value
        gate_payload["reason_codes"] = ["INSUFFICIENT_EVIDENCE"]
        adjusted_text = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
    return adjusted_text, gate_payload


def _run_pre_commit_ethics(
    *,
    draft_text: str,
    context_refs: list[str],
    generation_meta: dict[str, Any],
    source: Literal["user", "assistant", "system"],
    subject: Literal["reply", "action", "rule", "summary", "decision"],
) -> dict[str, Any]:
    gate_input = GateInput(
        draft_text=draft_text,
        task="commit",
        mode="json",
        risk_level=_derive_risk_level(draft_text),
        context_refs=context_refs,
        capabilities={"file_access": True},
        generation_meta=generation_meta,
        commit_allowed=True,
        commit_allowed_by="policy",
        source=source,
        subject=subject,
        facet="CANDIDATE",
    )
    gate_result = pre_commit_gate(gate_input)
    gate_payload = gate_result.model_dump(mode="json")
    if gate_result.outcome != EthicsOutcome.FIX or gate_result.commit_meta is None:
        reason = ",".join(gate_result.reason_codes or ["UNKNOWN"])
        raise HTTPException(status_code=409, detail=f"pre_commit_gate_blocked:{reason}")
    return gate_payload


def _request_generation_meta(
    request: Request,
    *,
    provider: str,
    model: str,
    route: str = "local",
    latency_ms: int = 0,
    trace_id: str | None = None,
    shortcuts_signature_valid: bool | None = None,
) -> dict[str, Any]:
    return build_generation_meta(
        {
            "provider": provider,
            "model": model,
            "route": route,
            "capabilities": {
                "web_access": False,
                "file_access": False,
                "exec_access": False,
                "device_actions": False,
            },
            "latency_ms": latency_ms,
            "trace_id": trace_id,
            "user_agent": request.headers.get("user-agent", ""),
            "headers": dict(request.headers),
            "shortcuts_signature_valid": shortcuts_signature_valid,
            "shortcuts_status": settings.shortcuts_integration_status,
        }
    )


def _request_trace_id(request: Request) -> str:
    for header in ("x-trace-id", "x-request-id"):
        value = (request.headers.get(header) or "").strip()
        if value:
            safe = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-")
            if safe:
                return safe[:128]
    return f"req_{uuid4().hex}"


def _is_shortcuts_request(request: Request) -> bool:
    ua = request.headers.get("user-agent", "").lower()
    source = request.headers.get("x-sophia-source", "").lower()
    if source in {"shortcuts", "siri_shortcuts", "apple_shortcuts"}:
        return True
    return "shortcuts" in ua or "siri" in ua


async def _verify_shortcuts_signature(request: Request) -> bool | None:
    if not _is_shortcuts_request(request):
        return None
    provided = request.headers.get("x-sophia-shortcut-signature", "").strip().lower()
    timestamp = request.headers.get("x-sophia-timestamp", "").strip()
    secret = (settings.shortcuts_secret or "").strip()
    if not provided or not secret:
        return False
    body = await request.body()
    expected_legacy = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest().lower()
    if hmac.compare_digest(provided, expected_legacy):
        return True

    # v1.1 preferred format:
    # HMAC_SHA256("{method}\n{path}\n{timestamp}\n{sha256(body)}", SHORTCUT_SECRET)
    if timestamp:
        body_hash = hashlib.sha256(body).hexdigest().lower()
        signing_string = "\n".join([request.method.upper(), request.url.path, timestamp, body_hash])
        expected_v11 = hmac.new(secret.encode("utf-8"), signing_string.encode("utf-8"), hashlib.sha256).hexdigest().lower()
        if hmac.compare_digest(provided, expected_v11):
            return True
    return False


def _shorten_text(value: str, *, max_chars: int = 180) -> str:
    return " ".join((value or "").split())[:max_chars]


def _parse_iso_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_recent(value: Any, *, days: int = 7) -> bool:
    dt = _parse_iso_dt(value)
    if dt is None:
        return False
    return (_utc_now() - dt) <= timedelta(days=days)


def _build_bitmap_summary(session) -> dict[str, Any]:
    bind = session.get_bind()
    if bind is None:
        return {"candidates": [], "anchors": []}

    try:
        inspector = sa_inspect(bind)
    except Exception:
        return {"candidates": [], "anchors": []}

    candidates: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    try:
        if inspector.has_table("candidates"):
            rows = session.execute(
                text(
                    """
                    SELECT candidate_id, note_thin, confidence, proposed_at
                    FROM candidates
                    ORDER BY proposed_at DESC
                    LIMIT 20
                    """
                )
            ).fetchall()
            for row in rows:
                proposed_at = row[3]
                if proposed_at is not None and not _is_recent(proposed_at, days=7):
                    continue
                parsed_proposed_at = _parse_iso_dt(proposed_at)
                candidates.append(
                    {
                        "id": str(row[0]),
                        "note": _shorten_text(str(row[1] or ""), max_chars=120),
                        "confidence": int(row[2] or 0),
                        "proposed_at": _to_iso(parsed_proposed_at) if parsed_proposed_at else "",
                    }
                )
                if len(candidates) >= 5:
                    break

        if inspector.has_table("backbones"):
            rows = session.execute(
                text(
                    """
                    SELECT backbone_id, combined_bits, role, adopted_at
                    FROM backbones
                    ORDER BY adopted_at DESC
                    LIMIT 20
                    """
                )
            ).fetchall()
            for row in rows:
                adopted_at = row[3]
                if adopted_at is not None and not _is_recent(adopted_at, days=7):
                    continue
                parsed_adopted_at = _parse_iso_dt(adopted_at)
                anchors.append(
                    {
                        "id": str(row[0]),
                        "bits": int(row[1] or 0),
                        "role": str(row[2] or ""),
                        "adopted_at": _to_iso(parsed_adopted_at) if parsed_adopted_at else "",
                    }
                )
                if len(anchors) >= 5:
                    break
    except Exception:
        return {"candidates": [], "anchors": []}

    return {"candidates": candidates, "anchors": anchors}


def build_chat_context(context_tag: str, session, payload: AddMessagePayload, user_text: str) -> dict[str, Any]:
    recent_rows = (
        session.query(ChatTimelineMessage)
        .filter(ChatTimelineMessage.context_tag == context_tag)
        .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
        .limit(10)
        .all()
    )
    recent = [
        {
            "role": row.role,
            "text": _shorten_text(row.content, max_chars=180),
            "status": row.status,
            "created_at": _to_iso(row.created_at),
        }
        for row in reversed(recent_rows)
    ]

    mind_rows = (
        session.query(MindItem)
        .order_by(MindItem.priority.desc(), MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(5)
        .all()
    )
    mind = [
        {
            "type": row.type,
            "title": _shorten_text(row.title, max_chars=80),
            "summary_120": _shorten_text(row.summary_120, max_chars=120),
            "priority": int(row.priority or 0),
            "risk_score": float(row.risk_score or 0.0),
            "confidence": float(row.confidence or 0.0),
        }
        for row in mind_rows
    ]

    user_rules = match_user_rules(session, user_text.strip(), limit=5)
    bitmap = _build_bitmap_summary(session)
    memory_lookup = mind_query_for_chat(session, user_text=user_text.strip(), context_tag=context_tag)

    return {
        "context_tag": context_tag,
        "linked_node": payload.linked_node,
        "linked_cluster": payload.linked_cluster,
        "recent_messages": recent,
        "mind_top": mind,
        "memory_lookup": memory_lookup,
        "user_rules": user_rules,
        "bitmap": bitmap,
    }


def _build_history_digest(session, *, context_tag: str, limit: int = 20) -> str:
    rows = (
        session.query(ChatTimelineMessage)
        .filter(ChatTimelineMessage.context_tag == context_tag)
        .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
        .limit(limit)
        .all()
    )
    lines: list[str] = []
    for row in reversed(rows):
        role = "U" if row.role == "user" else "S"
        lines.append(f"{role}:{_shorten_text(row.content, max_chars=60)}")
    return " | ".join(lines)


def _build_work_status_snapshot(session) -> dict[str, Any]:
    rows = (
        session.query(WorkPackage.status, func.count(WorkPackage.id))
        .group_by(WorkPackage.status)
        .all()
    )
    by_status = {str(status or "").upper(): int(count or 0) for status, count in rows}
    ready_count = by_status.get("READY", 0)
    in_progress_count = by_status.get("IN_PROGRESS", 0)
    recent_work = (
        session.query(WorkPackage)
        .order_by(WorkPackage.updated_at.desc(), WorkPackage.created_at.desc(), WorkPackage.id.desc())
        .first()
    )
    recent_work_title = str(recent_work.title or "").strip() if recent_work is not None else ""
    today = _utc_now().date().isoformat()
    notes_today = list_system_notes(db=session, date=today, limit=50)
    if notes_today:
        notes_status = f"생성 {len(notes_today)}건"
    else:
        notes_status = "생성 없음"
    return {
        "ready_count": ready_count,
        "in_progress_count": in_progress_count,
        "recent_work_title": recent_work_title,
        "notes_status": notes_status,
    }


def _try_unconscious_reply(session, *, context_tag: str, user_text: str) -> dict[str, Any] | None:
    history_digest = _build_history_digest(session, context_tag=context_tag, limit=20)
    signal = classify_unconscious_intent(user_text, history_digest)
    if signal is None:
        return None

    pattern_id = str(signal.get("pattern_id", "")).strip().upper()
    confidence = float(signal.get("confidence", 0.0) or 0.0)
    params = signal.get("params") if isinstance(signal.get("params"), dict) else {}
    params = dict(params)
    if pattern_id == "WORK_STATUS_QUERY":
        params.update(_build_work_status_snapshot(session))
    reply_text = render_unconscious_reply(pattern_id, params, persona_level=0)
    kind = "CLARIFY" if pattern_id == "UNKNOWN_BUT_ACTIONABLE" else "ANSWER"

    return {
        "pattern_id": pattern_id,
        "confidence": confidence,
        "params": params,
        "text": reply_text,
        "kind": kind,
        "sources": [{"type": "mind", "ref": f"unconscious:{pattern_id.lower()}"}],
        "history_digest": history_digest,
        "persona_level": 0,
    }


def _call_local_llm_contract(user_text: str, context: dict[str, Any]) -> str:
    llm = LLMInterface()
    schema_min = {
        "required": CHAT_CONTRACT_SCHEMA.get("required", []),
        "properties": CHAT_CONTRACT_SCHEMA.get("properties", {}),
    }
    system_prompt = "\n".join(
        [
            "You are Sophia local chat orchestrator.",
            "Return ONLY valid JSON. Never include markdown or prose.",
            "If uncertain, output kind=CLARIFY.",
            "Use schema chat_contract.v0.1 exactly.",
            "For CLARIFY, ask exactly one question.",
            "For ANSWER, include at least one source ref.",
            "For TASK_PLAN, keep 1~3 steps and do not execute.",
        ]
    )
    user_prompt = "\n".join(
        [
            "[chat_contract_schema]",
            json.dumps(schema_min, ensure_ascii=False),
            "",
            "[chat_context]",
            json.dumps(context, ensure_ascii=False),
            "",
            "[user_input]",
            user_text.strip(),
            "",
            "[output_rules]",
            "Output JSON object only.",
        ]
    )
    raw = llm._call_ollama(llm.primary_model, system_prompt, user_prompt)
    if raw:
        return raw
    fallback = llm._call_ollama(llm.fallback_model, system_prompt, user_prompt)
    return fallback or ""


def _find_latest_pending_clarify(session, *, context_tag: str) -> ChatTimelineMessage | None:
    row = (
        session.query(ChatTimelineMessage)
        .filter(
            ChatTimelineMessage.role == "sophia",
            ChatTimelineMessage.context_tag == context_tag,
            ChatTimelineMessage.status == "pending",
        )
        .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
        .first()
    )
    if row is None:
        return None
    meta = row.meta if isinstance(row.meta, dict) else {}
    if str(meta.get("kind", "")).upper() != "CLARIFY":
        return None
    return row


def _enqueue_task_plan(session, *, contract: dict[str, Any], context_tag: str, linked_node: str | None) -> str | None:
    task_plan = contract.get("task_plan")
    if not isinstance(task_plan, dict):
        return None
    steps = task_plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return None

    package_id = f"wp_{uuid4().hex}"
    row = WorkPackage(
        id=package_id,
        title="Chat Task Plan",
        description=_shorten_text(str(contract.get("text", "")), max_chars=240),
        payload={
            "work_packet": {
                "id": package_id,
                "kind": "IMPLEMENT",
                "context_tag": "work",
                "linked_node": linked_node,
                "acceptance_criteria": ["승인 후 IDE 전달", "실행은 별도 report 경로로 처리"],
                "deliverables": ["return_payload.json"],
                "return_payload_spec": {"status": "DONE|BLOCKED|FAILED", "signals": [], "artifacts": [], "notes": ""},
                "steps": steps,
            }
        },
        context_tag="work",
        status="READY",
        linked_node=linked_node,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(row)
    session.flush()
    return package_id


def _extract_question_signals(content: str) -> list[dict[str, Any]]:
    text = content.strip().lower()
    signals: list[dict[str, Any]] = []
    for rule in QUESTION_SIGNAL_RULES:
        patterns = rule["patterns"]
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            signals.append(rule)
    return signals


def _enqueue_question_if_ready(session, pool: QuestionPool) -> ChatTimelineMessage | None:
    if pool.hit_count < 3 and float(pool.risk_score or 0.0) < 0.8:
        return None

    pending_exists = (
        session.query(ChatTimelineMessage)
        .filter(
            ChatTimelineMessage.role == "sophia",
            ChatTimelineMessage.status == "pending",
            ChatTimelineMessage.linked_cluster == pool.cluster_id,
        )
        .first()
    )
    if pending_exists:
        pool.status = "pending"
        session.add(pool)
        return None

    linked_node = None
    linked_nodes = list(pool.linked_nodes or [])
    if linked_nodes:
        linked_node = str(linked_nodes[0])

    message = _save_message(
        session=session,
        role="sophia",
        content=_build_question_prompt(pool.cluster_id),
        context_tag="question-queue",
        importance=max(float(pool.risk_score or 0.0), 0.8),
        linked_cluster=pool.cluster_id,
        linked_node=linked_node,
        status="pending",
    )
    pool.status = "pending"
    pool.last_asked_at = _utc_now()
    pool.asked_count = int(pool.asked_count or 0) + 1
    session.add(pool)
    write_lifecycle_event(
        "QUESTION_ASKED",
        {
            "cluster_id": pool.cluster_id,
            "asked_count": int(pool.asked_count or 0),
            "risk_score": float(pool.risk_score or 0.0),
            "message_id": message.id,
        },
    )
    return message


def _on_question_ready(session, pool: QuestionPool) -> None:
    ingest_trigger_event(
        session,
        event_type="QUESTION_READY",
        payload={
            "cluster_id": pool.cluster_id,
            "hit_count": int(pool.hit_count or 0),
            "risk_score": float(pool.risk_score or 0.0),
        },
    )
    diary_payload = maybe_build_daily_diary(session)
    if diary_payload is not None:
        append_system_note(
            db=session,
            note_type=str(diary_payload["note_type"]),
            source_events=list(diary_payload["source_events"]),
            summary=str(diary_payload["summary"]),
            body_markdown=str(diary_payload["body_markdown"]),
            status=str(diary_payload["status"]),
            actionables=list(diary_payload["actionables"]),
            badge=str(diary_payload["badge"]),
            dedup_key=str(diary_payload["dedup_key"]),
        )


def _upsert_question_signal(
    *,
    session,
    cluster_id: str,
    description: str,
    risk_score: float,
    snippet: str | None = None,
    source: str | None = None,
    evidence_timestamp: str | None = None,
    linked_node: str | None = None,
) -> tuple[QuestionPool, ChatTimelineMessage | None]:
    return upsert_question_signal_service(
        session=session,
        cluster_id=cluster_id,
        description=description,
        risk_score=risk_score,
        snippet=snippet,
        source=source,
        evidence_timestamp=evidence_timestamp,
        linked_node=linked_node,
        write_event=write_lifecycle_event,
        on_question_ready=_on_question_ready,
        enqueue_if_ready=_enqueue_question_if_ready,
    )


def _ensure_legacy_backfill(session) -> None:
    global _legacy_backfilled
    if _legacy_backfilled:
        return

    existing = session.query(func.count(ChatTimelineMessage.id)).scalar() or 0
    if existing > 0:
        _legacy_backfilled = True
        return

    if not LEGACY_CHAT_LOG_DIR.exists():
        _legacy_backfilled = True
        return

    rows_added = 0
    for path in sorted(LEGACY_CHAT_LOG_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue

                role_raw = str(payload.get("role", "")).strip().lower()
                role = "user" if role_raw == "user" else "sophia"
                content = str(payload.get("content", "")).strip()
                if not content:
                    continue
                created_at_raw = payload.get("timestamp")
                created_at = _utc_now()
                if isinstance(created_at_raw, str) and created_at_raw.strip():
                    parsed = created_at_raw.strip()
                    if parsed.endswith("Z"):
                        parsed = parsed[:-1] + "+00:00"
                    try:
                        created_at = datetime.fromisoformat(parsed)
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=UTC)
                        created_at = created_at.astimezone(UTC)
                    except ValueError:
                        created_at = _utc_now()

                _save_message(
                    session=session,
                    role=role,
                    content=content,
                    context_tag="system",
                    importance=_calc_importance(content),
                    status="normal",
                    created_at=created_at,
                )
                rows_added += 1

    session.commit()
    _legacy_backfilled = True
    if rows_added:
        print(f"[chat_router] Backfilled {rows_added} legacy chat messages")


@router.post("/message")
async def send_message(payload: ChatMessagePayload, request: Request):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        shortcuts_signature_valid = await _verify_shortcuts_signature(request)
        request_trace_id = _request_trace_id(request)

        print("CTX_IN:", payload.context_tag, "trace_id=", request_trace_id)
        context_tag = _normalize_context_tag(payload.context_tag or "chat")
        print("CTX_SAVED:", context_tag, "trace_id=", request_trace_id)
        if context_tag == "system":
            raise HTTPException(status_code=400, detail="context_tag 'system' is reserved for internal events")
        user_message = _save_message(
            session=session,
            role="user",
            content=payload.content.strip(),
            context_tag=context_tag,
            importance=_calc_importance(payload.content, payload.importance),
            linked_node=payload.linked_node,
            status="normal",
        )

        pending_messages: list[ChatTimelineMessage] = []
        signals = _extract_question_signals(payload.content)
        for signal in signals:
            _, pending = _upsert_question_signal(
                session=session,
                cluster_id=str(signal["cluster_id"]),
                description=str(signal["description"]),
                risk_score=float(signal["risk_score"]),
                snippet=payload.content[:200],
                source="chat.message",
                evidence_timestamp=_to_iso(_utc_now()),
                linked_node=payload.linked_node,
            )
            if pending:
                pending_messages.append(pending)

        payload_like = AddMessagePayload(
            role="user",
            content=payload.content,
            context_tag=context_tag,
            linked_node=payload.linked_node,
        )
        chat_context = build_chat_context(context_tag, session, payload_like, payload.content)
        reply_bundle = generate_chat_reply(
            user_text=payload.content.strip(),
            context=chat_context,
            llm_call=_call_local_llm_contract,
        )
        reply_text = str(reply_bundle.get("text", "")).strip()
        memory_hits = list(reply_bundle.get("memory_hits", []))[:5]
        memory_used = bool(reply_bundle.get("memory_used", False))
        generation_meta = _request_generation_meta(
            request,
            provider="mock",
            model="local_brain_template",
            route="local",
            latency_ms=0,
            trace_id=request_trace_id,
            shortcuts_signature_valid=shortcuts_signature_valid,
        )
        reply_text, output_ethics = _apply_pre_output_ethics(
            draft_text=reply_text,
            context_tag=context_tag,
            generation_meta=generation_meta,
            user_rules=match_user_rules(session, payload.content.strip(), limit=5),
        )
        log_generation_line(generation_meta)
        sophia_message = _save_message(
            session=session,
            role="sophia",
            content=reply_text,
            context_tag=context_tag,
            importance=_calc_importance(reply_text),
            meta=attach_generation_meta(
                {
                    "ethics": output_ethics,
                    "kind": reply_bundle.get("kind", "ANSWER"),
                    "needs": reply_bundle.get("needs"),
                    "sources": reply_bundle.get("sources", []),
                    "confidence_model": reply_bundle.get("confidence_model", 0.0),
                    "fallback_applied": bool(reply_bundle.get("fallback_applied", False)),
                    "fallback_reason": reply_bundle.get("fallback_reason", ""),
                    "persona_stage": reply_bundle.get("persona_stage", "early"),
                    "memory_hits": memory_hits,
                    "memory_used": memory_used,
                },
                generation_meta,
            ),
            status="normal",
        )

        commit_ethics = _run_pre_commit_ethics(
            draft_text="\n".join([payload.content.strip(), reply_text]),
            context_refs=[context_tag, user_message.id, sophia_message.id],
            generation_meta=generation_meta,
            source="assistant",
            subject="reply",
        )
        write_lifecycle_event(
            "ETHICS_FIX_COMMITTED",
            {
                "project": "sophia",
                "endpoint": "/chat/message",
                "task": "chat.reply",
                "trace_id": generation_meta.get("trace_id", request_trace_id),
                "provider_final": "local",
                "fallback_applied": False,
                "gate_reason": ",".join(commit_ethics.get("reason_codes", [])),
                "generation": generation_meta,
                "ethics": commit_ethics,
            },
            skill_id="ethics.gate",
        )
        session.commit()
        return {
            "status": "ok",
            "reply": reply_text,
            "context_tag": context_tag,
            "trace_id": generation_meta.get("trace_id", request_trace_id),
            "messages": [_serialize_message(user_message), _serialize_message(sophia_message)],
            "pending_inserted": [_serialize_message(m) for m in pending_messages],
            "memory_hits": memory_hits,
            "memory_used": memory_used,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@router.post("/messages")
async def add_message(payload: AddMessagePayload, request: Request):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        shortcuts_signature_valid = await _verify_shortcuts_signature(request)
        request_trace_id = _request_trace_id(request)
        input_text = (payload.content if payload.content is not None else payload.message) or ""
        content_text = str(input_text).strip()
        if not content_text:
            raise HTTPException(status_code=400, detail="content is required")
        incoming_context = payload.context_tag if payload.context_tag is not None else payload.mode
        print("CTX_IN:", incoming_context, "trace_id=", request_trace_id)
        context_tag = _normalize_context_tag(incoming_context or "chat")
        print("CTX_SAVED:", context_tag, "trace_id=", request_trace_id)
        if payload.role == "user" and context_tag == "system":
            raise HTTPException(status_code=400, detail="context_tag 'system' is reserved for internal events")
        row = _save_message(
            session=session,
            role=payload.role,
            content=content_text,
            context_tag=context_tag,
            importance=float(payload.importance),
            emotion_signal=payload.emotion_signal,
            linked_cluster=payload.linked_cluster,
            linked_node=payload.linked_node,
            status=payload.status,
        )

        learned_rule: dict[str, Any] | None = None
        if payload.role == "user":
            latest_clarify = _find_latest_pending_clarify(session, context_tag=context_tag)
            if latest_clarify is not None:
                learned_rule = learn_from_clarify_response(
                    session,
                    clarify_meta=latest_clarify.meta if isinstance(latest_clarify.meta, dict) else {},
                    user_text=content_text,
                )
                if learned_rule is not None:
                    latest_clarify.status = "resolved"
                    session.add(latest_clarify)

            learning_signals = collect_learning_signals(
                session,
                context_tag=context_tag,
                user_text=content_text,
                learned_rule=learned_rule,
            )
            if learning_signals.term_mapping is not None:
                learning_signals.term_mapping["trace_id"] = request_trace_id
                ingest_trigger_event(
                    session,
                    event_type="TERM_MAPPING",
                    payload=learning_signals.term_mapping,
                )
            if learning_signals.topic_seen is not None:
                learning_signals.topic_seen["trace_id"] = request_trace_id
                ingest_trigger_event(
                    session,
                    event_type="TOPIC_SEEN",
                    payload=learning_signals.topic_seen,
                )
            if learning_signals.user_preference is not None:
                learning_signals.user_preference["trace_id"] = request_trace_id
                ingest_trigger_event(
                    session,
                    event_type="USER_PREFERENCE",
                    payload=learning_signals.user_preference,
                )

        reply_message: ChatTimelineMessage | None = None
        task_plan_work_id: str | None = None
        llm_gate: dict[str, Any] | None = None
        memory_hits: list[str] = []
        memory_used = False
        if _should_auto_reply(payload.role, context_tag):
            unconscious = _try_unconscious_reply(
                session,
                context_tag=context_tag,
                user_text=content_text,
            )
            if unconscious is not None:
                reply_kind = str(unconscious.get("kind", "ANSWER")).upper()
                reply_text = str(unconscious.get("text", "")).strip()
                confidence = float(unconscious.get("confidence", 0.0) or 0.0)
                pattern_id = str(unconscious.get("pattern_id", "UNKNOWN")).strip().upper()
                llm_gate = {
                    "pass": True,
                    "reason": "unconscious_hit",
                    "gate_score": confidence,
                    "evidence_scope": "narrow",
                    "schema_errors": [],
                    "fallback_applied": False,
                }
                generation_meta = _request_generation_meta(
                    request,
                    provider="rule",
                    model="unconscious_v0",
                    route="local",
                    latency_ms=0,
                    trace_id=request_trace_id,
                    shortcuts_signature_valid=shortcuts_signature_valid,
                )
                reply_text, output_ethics = _apply_pre_output_ethics(
                    draft_text=reply_text,
                    context_tag=context_tag,
                    generation_meta=generation_meta,
                    user_rules=match_user_rules(session, content_text, limit=5),
                )
                reply_status = "pending" if reply_kind == "CLARIFY" else "normal"
                reply_meta = attach_generation_meta(
                    {
                        "schema": CHAT_CONTRACT_SCHEMA.get("title", "chat_contract.v0.1"),
                        "kind": reply_kind,
                        "needs": {"type": "meaning", "options": []} if reply_kind == "CLARIFY" else None,
                        "task_plan": None,
                        "sources": unconscious.get("sources", []),
                        "confidence_model": confidence,
                        "gate_score": llm_gate.get("gate_score"),
                        "evidence_scope": llm_gate.get("evidence_scope"),
                        "gate_reason": llm_gate.get("reason", ""),
                        "fallback_applied": False,
                        "fallback_reason": "",
                        "persona_stage": "early",
                        "call_user": "주인님",
                        "memory_hits": [],
                        "memory_used": False,
                        "unconscious": {
                            "pattern_id": pattern_id,
                            "confidence": confidence,
                            "persona_level": int(unconscious.get("persona_level", 0) or 0),
                        },
                        "ethics": output_ethics,
                    },
                    generation_meta,
                )
                log_generation_line(generation_meta)
                reply_message = _save_message(
                    session=session,
                    role="sophia",
                    content=reply_text,
                    context_tag=context_tag,
                    importance=_calc_importance(reply_text),
                    emotion_signal=reply_kind.lower(),
                    meta=reply_meta,
                    status=reply_status,
                )
                ingest_trigger_event(
                    session,
                    event_type="UNCONSCIOUS_HIT",
                    payload={
                        "pattern_id": pattern_id,
                        "confidence": confidence,
                        "context_tag": context_tag,
                        "summary": _shorten_text(reply_text, max_chars=120),
                        "trace_id": request_trace_id,
                    },
                )
                ingest_trigger_event(
                    session,
                    event_type="UNCONSCIOUS_PATTERN_SEEN",
                    payload={
                        "pattern_id": pattern_id,
                        "day": _utc_now().date().isoformat(),
                        "count": 1,
                        "trace_id": request_trace_id,
                    },
                )
            else:
                chat_context = build_chat_context(context_tag, session, payload, content_text)
                llm_started = time.perf_counter()
                reply_bundle = generate_chat_reply(
                    user_text=content_text,
                    context=chat_context,
                    llm_call=_call_local_llm_contract,
                )
                latency_ms = int((time.perf_counter() - llm_started) * 1000)
                llm_gate = reply_bundle.get("gate", {}) if isinstance(reply_bundle.get("gate"), dict) else {}
                reply_text = str(reply_bundle.get("text", "")).strip()
                reply_kind = str(reply_bundle.get("kind", "CLARIFY")).upper()
                memory_hits = list(reply_bundle.get("memory_hits", []))[:5]
                memory_used = bool(reply_bundle.get("memory_used", False))
                generation_meta = _request_generation_meta(
                    request,
                    provider="ollama",
                    model="unknown",
                    route="local",
                    latency_ms=latency_ms,
                    trace_id=request_trace_id,
                    shortcuts_signature_valid=shortcuts_signature_valid,
                )
                reply_text, output_ethics = _apply_pre_output_ethics(
                    draft_text=reply_text,
                    context_tag=context_tag,
                    generation_meta=generation_meta,
                    user_rules=chat_context.get("user_rules", []) if isinstance(chat_context, dict) else [],
                )
                reply_status = "pending" if reply_kind == "CLARIFY" else "normal"
                if reply_kind == "TASK_PLAN":
                    task_plan_work_id = _enqueue_task_plan(
                        session,
                        contract={
                            "text": reply_text,
                            "task_plan": reply_bundle.get("task_plan"),
                        },
                        context_tag=context_tag,
                        linked_node=payload.linked_node,
                    )
                reply_meta = {
                    "schema": CHAT_CONTRACT_SCHEMA.get("title", "chat_contract.v0.1"),
                    "kind": reply_kind,
                    "needs": reply_bundle.get("needs"),
                    "task_plan": reply_bundle.get("task_plan"),
                    "sources": reply_bundle.get("sources"),
                    "confidence_model": reply_bundle.get("confidence_model"),
                    "gate_score": llm_gate.get("gate_score"),
                    "evidence_scope": llm_gate.get("evidence_scope"),
                    "gate_reason": llm_gate.get("reason", ""),
                    "fallback_applied": bool(reply_bundle.get("fallback_applied", False)),
                    "fallback_reason": reply_bundle.get("fallback_reason", ""),
                    "persona_stage": reply_bundle.get("persona_stage", "early"),
                    "call_user": reply_bundle.get("call_user", "주인님"),
                    "memory_hits": memory_hits,
                    "memory_used": memory_used,
                    "ethics": output_ethics,
                }
                if task_plan_work_id:
                    reply_meta["work_package_id"] = task_plan_work_id
                reply_meta = attach_generation_meta(reply_meta, generation_meta)
                log_generation_line(generation_meta)
                reply_message = _save_message(
                    session=session,
                    role="sophia",
                    content=reply_text,
                    context_tag=context_tag,
                    importance=_calc_importance(reply_text),
                    emotion_signal=reply_kind.lower(),
                    meta=reply_meta,
                    status=reply_status,
                )

        if payload.role == "user" and payload.linked_cluster:
            analysis = analyze_to_forest(
                project_name="sophia",
                doc_name=f"question_response_{payload.linked_cluster}_{_utc_now().strftime('%Y%m%d_%H%M%S')}.md",
                content=content_text,
                target=payload.linked_node or payload.linked_cluster,
                change=f"question response: {payload.linked_cluster}",
                scope="",
                write_doc=False,
            )
            for signal in analysis.get("signals", []):
                _upsert_question_signal(
                    session=session,
                    cluster_id=str(signal["cluster_id"]),
                    description=str(signal["description"]),
                    risk_score=float(signal["risk_score"]),
                    snippet=content_text[:200],
                    source=f"question.response:{payload.linked_cluster}",
                    evidence_timestamp=_to_iso(_utc_now()),
                    linked_node=payload.linked_node,
                )

            lowered = content_text.lower()
            if any(token in lowered for token in ["확정", "결정", "resolved", "완료", "정의", "명시"]):
                qrow = session.query(QuestionPool).filter(QuestionPool.cluster_id == payload.linked_cluster).one_or_none()
                if qrow is not None:
                    qrow.status = "resolved"
                    session.add(qrow)
                    related = (
                        session.query(ChatTimelineMessage)
                        .filter(
                            ChatTimelineMessage.linked_cluster == payload.linked_cluster,
                            ChatTimelineMessage.status.in_(["pending", "acknowledged", "read"]),
                        )
                        .all()
                    )
                    for message in related:
                        message.status = "resolved"
                        session.add(message)
                    write_lifecycle_event(
                        "QUESTION_RESOLVED",
                        {
                            "project": "sophia",
                            "cluster_id": payload.linked_cluster,
                            "messages_updated": len(related),
                            "question_status": qrow.status,
                        },
                    )

            write_lifecycle_event(
                "QUESTION_RESPONSE_ANALYZED",
                {
                    "project": "sophia",
                    "cluster_id": payload.linked_cluster,
                    "signals": len(analysis.get("signals", [])),
                    "source_doc": analysis.get("doc_name", ""),
                },
            )

            append_system_note(
                db=session,
                note_type="QUESTION_RESPONSE_DIGEST",
                source_events=["QUESTION_RESPONSE_ANALYZED"],
                summary=f"{payload.linked_cluster} 질문 응답이 반영되었습니다.",
                body_markdown="\n".join(
                    [
                        f"- linked_cluster: {payload.linked_cluster}",
                        f"- signals: {len(analysis.get('signals', []))}",
                        f"- resolved_hint: {str(any(token in lowered for token in ['확정', '결정', 'resolved', '완료', '정의', '명시'])).lower()}",
                    ]
                ),
                status="ACTIVE",
                actionables=[{"type": "open_question_queue", "cluster_id": payload.linked_cluster}],
                linked_cluster_id=payload.linked_cluster,
                risk_score=max(
                    [float(item.get("risk_score", 0.0)) for item in analysis.get("signals", []) if isinstance(item, dict)],
                    default=0.0,
                ),
                badge="QUESTION_READY",
                dedup_key=f"question_response:{payload.linked_cluster}:{content_text}",
            )
        commit_text_parts = [content_text]
        context_refs = [context_tag, row.id]
        if reply_message is not None:
            commit_text_parts.append(reply_message.content)
            context_refs.append(reply_message.id)
            commit_generation_meta = (reply_message.meta or {}).get("generation") if isinstance(reply_message.meta, dict) else None
        else:
            commit_generation_meta = _request_generation_meta(
                request,
                provider="mock",
                model="chat_timeline_append",
                route="local",
                latency_ms=0,
                trace_id=request_trace_id,
                shortcuts_signature_valid=shortcuts_signature_valid,
            )
        commit_ethics = _run_pre_commit_ethics(
            draft_text="\n".join(commit_text_parts),
            context_refs=context_refs,
            generation_meta=commit_generation_meta,
            source="assistant" if reply_message is not None else "user",
            subject="reply" if reply_message is not None else "action",
        )
        write_lifecycle_event(
            "ETHICS_FIX_COMMITTED",
            {
                "project": "sophia",
                "endpoint": "/chat/messages",
                "task": "chat.timeline_append",
                "trace_id": commit_generation_meta.get("trace_id", request_trace_id),
                "provider_final": "local",
                "fallback_applied": False,
                "gate_reason": ",".join(commit_ethics.get("reason_codes", [])),
                "generation": commit_generation_meta,
                "ethics": commit_ethics,
            },
            skill_id="ethics.gate",
        )
        session.commit()

        if learned_rule is not None:
            write_lifecycle_event(
                "USER_RULE_LEARNED",
                {
                    "project": "sophia",
                    "context_tag": context_tag,
                    "rule_key": learned_rule.get("key", ""),
                    "rule_type": learned_rule.get("type", ""),
                    "rule_id": learned_rule.get("id", 0),
                },
                skill_id="chat.learning",
            )
        if task_plan_work_id is not None:
            write_lifecycle_event(
                "WORK_PACKAGE_CREATED",
                {
                    "project": "sophia",
                    "id": task_plan_work_id,
                    "kind": "IMPLEMENT",
                    "context_tag": "work",
                    "source": "chat.task_plan",
                },
                skill_id="chat.autoplan",
            )

        messages = [_serialize_message(row)]
        if reply_message is not None:
            messages.append(_serialize_message(reply_message))
        return {
            "status": "ok",
            "message": _serialize_message(row),
            "messages": messages,
            "context_tag": context_tag,
            "trace_id": (commit_generation_meta or {}).get("trace_id", request_trace_id),
            "reply_skipped": bool(payload.role == "user" and context_tag == "system"),
            "gate": llm_gate or {},
            "task_plan_work_id": task_plan_work_id,
            "learned_rule": learned_rule,
            "memory_hits": memory_hits,
            "memory_used": memory_used,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@router.get("/history")
async def get_history(
    context_tag: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=2000),
):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        query = session.query(ChatTimelineMessage)
        if context_tag:
            raw = context_tag.strip().lower()
            if raw.endswith(":*"):
                prefix_raw = raw[:-2].strip()
                if prefix_raw == "forest":
                    query = query.filter(ChatTimelineMessage.context_tag.like("forest:%"))
                    rows = (
                        query.order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
                        .limit(limit)
                        .all()
                    )
                    rows.reverse()
                    return [_serialize_message(row) for row in rows]
                prefix = _normalize_context_tag(prefix_raw)
                query = query.filter(ChatTimelineMessage.context_tag.like(f"{prefix}:%"))
            else:
                normalized = _normalize_context_tag(raw)
                query = query.filter(ChatTimelineMessage.context_tag == normalized)

        rows = query.order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc()).limit(limit).all()
        rows.reverse()
        return [_serialize_message(row) for row in rows]
    finally:
        session.close()


@router.get("/contexts")
async def list_contexts():
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        rows = (
            session.query(ChatTimelineMessage.context_tag, func.count(ChatTimelineMessage.id))
            .group_by(ChatTimelineMessage.context_tag)
            .order_by(func.count(ChatTimelineMessage.id).desc(), ChatTimelineMessage.context_tag.asc())
            .all()
        )
        return [{"context_tag": context_tag, "count": int(count)} for context_tag, count in rows]
    finally:
        session.close()


@router.get("/pending")
async def list_pending(limit: int = Query(default=50, ge=1, le=500)):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        rows = (
            session.query(ChatTimelineMessage)
            .filter(
                ChatTimelineMessage.role == "sophia",
                ChatTimelineMessage.status == "pending",
            )
            .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [_serialize_message(row) for row in rows]
    finally:
        session.close()


@router.post("/questions/signal")
async def push_question_signal(payload: QuestionSignalPayload):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        pool, pending = _upsert_question_signal(
            session=session,
            cluster_id=payload.cluster_id.strip(),
            description=payload.description.strip(),
            risk_score=float(payload.risk_score),
            snippet=payload.snippet,
            source=payload.source,
            evidence_timestamp=payload.timestamp,
            linked_node=payload.linked_node,
        )
        session.commit()
        return {
            "status": "ok",
            "question_pool": {
                "cluster_id": pool.cluster_id,
                "description": pool.description,
                "hit_count": pool.hit_count,
                "risk_score": float(pool.risk_score),
                "evidence": pool.evidence or [],
                "linked_nodes": pool.linked_nodes or [],
                "status": pool.status,
                "last_triggered_at": _to_iso(pool.last_triggered_at) if pool.last_triggered_at else "",
                "last_asked_at": _to_iso(pool.last_asked_at) if pool.last_asked_at else "",
                "asked_count": int(pool.asked_count or 0),
            },
            "pending_inserted": _serialize_message(pending) if pending else None,
        }
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@router.post("/questions/{cluster_id}/ack")
async def ack_question(cluster_id: str):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        row = session.query(QuestionPool).filter(QuestionPool.cluster_id == cluster_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"question cluster not found: {cluster_id}")

        if row.status in {"collecting", "ready_to_ask", "pending"}:
            row.status = "acknowledged"
            session.add(row)

        updated = (
            session.query(ChatTimelineMessage)
            .filter(
                ChatTimelineMessage.linked_cluster == cluster_id,
                ChatTimelineMessage.status == "pending",
            )
            .all()
        )
        for message in updated:
            message.status = "acknowledged"
            session.add(message)

        session.commit()
        write_lifecycle_event(
            "QUESTION_ACKNOWLEDGED",
            {
                "cluster_id": cluster_id,
                "question_status": row.status,
                "messages_updated": len(updated),
            },
        )
        return {
            "status": "ok",
            "cluster_id": cluster_id,
            "question_status": row.status,
            "messages_updated": len(updated),
        }
    finally:
        session.close()


@router.post("/questions/{cluster_id}/resolve")
async def resolve_question(cluster_id: str):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        row = session.query(QuestionPool).filter(QuestionPool.cluster_id == cluster_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"question cluster not found: {cluster_id}")

        row.status = "resolved"
        session.add(row)

        related = (
            session.query(ChatTimelineMessage)
            .filter(
                ChatTimelineMessage.linked_cluster == cluster_id,
                ChatTimelineMessage.status.in_(["pending", "acknowledged", "read"]),
            )
            .all()
        )
        for message in related:
            message.status = "resolved"
            session.add(message)

        session.commit()
        write_lifecycle_event(
            "QUESTION_RESOLVED",
            {
                "cluster_id": cluster_id,
                "messages_updated": len(related),
                "question_status": row.status,
            },
        )
        return {
            "status": "ok",
            "cluster_id": cluster_id,
            "question_status": row.status,
            "messages_updated": len(related),
        }
    finally:
        session.close()


@router.post("/messages/{message_id}/read")
async def mark_message_read(message_id: str):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        row = session.query(ChatTimelineMessage).filter(ChatTimelineMessage.id == message_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"message not found: {message_id}")

        if row.status == "pending":
            row.status = "read"
            session.add(row)
            session.commit()
        else:
            session.commit()

        write_lifecycle_event(
            "MESSAGE_READ",
            {
                "message_id": message_id,
                "status": row.status,
                "linked_cluster": row.linked_cluster,
            },
        )
        return {"status": "ok", "message": _serialize_message(row)}
    finally:
        session.close()


@router.get("/questions/pool")
async def list_question_pool():
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        rows = (
            session.query(QuestionPool)
            .order_by(QuestionPool.risk_score.desc(), QuestionPool.hit_count.desc(), QuestionPool.cluster_id.asc())
            .all()
        )
        return [
            {
                "cluster_id": row.cluster_id,
                "description": row.description,
                "hit_count": int(row.hit_count or 0),
                "risk_score": float(row.risk_score or 0.0),
                "evidence": row.evidence or [],
                "linked_nodes": row.linked_nodes or [],
                "status": row.status,
                "last_triggered_at": _to_iso(row.last_triggered_at) if row.last_triggered_at else "",
                "last_asked_at": _to_iso(row.last_asked_at) if row.last_asked_at else "",
                "asked_count": int(row.asked_count or 0),
            }
            for row in rows
        ]
    finally:
        session.close()
