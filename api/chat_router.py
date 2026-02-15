from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect as sa_inspect, text

from api.config import settings
from api.ledger_events import write_lifecycle_event
from api.sophia_notes import append_system_note
from core.chat.chat_contract import CHAT_CONTRACT_SCHEMA, make_clarify_contract
from core.chat.chat_gate import parse_validate_and_gate
from core.chat.user_rules_store import learn_from_clarify_response, match_user_rules
from core.engine.local_brain import (
    build_intent_reply as local_build_intent_reply,
    build_question_prompt as local_build_question_prompt,
    classify_intent as local_classify_intent,
)
from core.forest.grove import analyze_to_forest
from core.llm_interface import LLMInterface
from core.memory.schema import ChatTimelineMessage, MindItem, QuestionPool, WorkPackage, create_session_factory
from sophia_kernel.modules.mind_diary import ingest_trigger_event, maybe_build_daily_diary

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
    role: Literal["user", "sophia"]
    content: str = Field(min_length=1)
    context_tag: str = "chat"
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


def _classify_intent(content: str) -> str:
    return local_classify_intent(content)


def _build_template_reply(intent: str, seed_text: str) -> str:
    return local_build_intent_reply(intent, seed_text)


def _build_question_prompt(cluster_id: str) -> str:
    return local_build_question_prompt(cluster_id)


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


def build_chat_context(context_tag: str, session, payload: AddMessagePayload) -> dict[str, Any]:
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

    user_rules = match_user_rules(session, payload.content.strip(), limit=5)
    bitmap = _build_bitmap_summary(session)

    return {
        "context_tag": context_tag,
        "linked_node": payload.linked_node,
        "linked_cluster": payload.linked_cluster,
        "recent_messages": recent,
        "mind_top": mind,
        "user_rules": user_rules,
        "bitmap": bitmap,
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


def _normalize_evidence(
    *,
    snippet: str | None,
    source: str | None,
    timestamp: str | None = None,
) -> dict[str, str]:
    return {
        "snippet": (snippet or "").strip()[:400],
        "source": (source or "").strip()[:200],
        "timestamp": (timestamp or _to_iso(_utc_now())).strip(),
    }


def _dedupe_evidence(items: list[dict[str, str]], max_items: int = 50) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in reversed(items):
        key = f"{item.get('snippet','')}|{item.get('source','')}|{item.get('timestamp','')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max_items:
            break
    result.reverse()
    return result


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
    row = session.query(QuestionPool).filter(QuestionPool.cluster_id == cluster_id).one_or_none()
    now = _utc_now()
    if row is None:
        row = QuestionPool(
            cluster_id=cluster_id,
            description=description,
            hit_count=0,
            risk_score=0.0,
            evidence=[],
            linked_nodes=[],
            status="collecting",
            last_triggered_at=now,
            asked_count=0,
        )
        session.add(row)
        session.flush()

    if row.status == "resolved":
        row.hit_count = 0
        row.risk_score = 0.0
        row.evidence = []
        row.status = "collecting"

    row.hit_count = int(row.hit_count or 0) + 1
    row.risk_score = max(float(row.risk_score or 0.0), float(risk_score))
    row.description = description
    row.last_triggered_at = now

    evidence = list(row.evidence or [])
    evidence.append(
        _normalize_evidence(
            snippet=snippet,
            source=source,
            timestamp=evidence_timestamp,
        )
    )
    row.evidence = _dedupe_evidence(evidence)

    linked_nodes = list(row.linked_nodes or [])
    if linked_node and linked_node not in linked_nodes:
        linked_nodes.append(linked_node)
    row.linked_nodes = linked_nodes

    threshold_met = row.hit_count >= 3 or float(row.risk_score) >= 0.8
    previous_status = str(row.status or "collecting")
    if threshold_met and previous_status == "collecting":
        row.status = "ready_to_ask"
        write_lifecycle_event(
            "QUESTION_READY",
            {
                "cluster_id": row.cluster_id,
                "hit_count": int(row.hit_count or 0),
                "risk_score": float(row.risk_score or 0.0),
            },
        )
        ingest_trigger_event(
            session,
            event_type="QUESTION_READY",
            payload={
                "cluster_id": row.cluster_id,
                "hit_count": int(row.hit_count or 0),
                "risk_score": float(row.risk_score or 0.0),
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
    elif not threshold_met and previous_status not in {"pending", "acknowledged", "resolved"}:
        row.status = "collecting"

    session.add(row)
    session.flush()

    write_lifecycle_event(
        "QUESTION_SIGNAL",
        {
            "cluster_id": row.cluster_id,
            "hit_count": int(row.hit_count or 0),
            "risk_score": float(row.risk_score or 0.0),
            "status": row.status,
        },
    )

    pending = _enqueue_question_if_ready(session, row)
    return row, pending


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
async def send_message(payload: ChatMessagePayload):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)

        print("CTX_IN:", payload.context_tag)
        context_tag = _normalize_context_tag(payload.context_tag or "chat")
        print("CTX_SAVED:", context_tag)
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

        intent = _classify_intent(payload.content)
        reply_text = _build_template_reply(intent, payload.content)
        sophia_message = _save_message(
            session=session,
            role="sophia",
            content=reply_text,
            context_tag=context_tag,
            importance=_calc_importance(reply_text),
            status="normal",
        )

        session.commit()
        return {
            "status": "ok",
            "reply": reply_text,
            "context_tag": context_tag,
            "messages": [_serialize_message(user_message), _serialize_message(sophia_message)],
            "pending_inserted": [_serialize_message(m) for m in pending_messages],
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
async def add_message(payload: AddMessagePayload):
    session = session_factory()
    try:
        _ensure_legacy_backfill(session)
        print("CTX_IN:", payload.context_tag)
        context_tag = _normalize_context_tag(payload.context_tag or "chat")
        print("CTX_SAVED:", context_tag)
        if payload.role == "user" and context_tag == "system":
            raise HTTPException(status_code=400, detail="context_tag 'system' is reserved for internal events")
        row = _save_message(
            session=session,
            role=payload.role,
            content=payload.content.strip(),
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
                    user_text=payload.content.strip(),
                )
                if learned_rule is not None:
                    latest_clarify.status = "resolved"
                    session.add(latest_clarify)

        reply_message: ChatTimelineMessage | None = None
        task_plan_work_id: str | None = None
        llm_gate: dict[str, Any] | None = None
        if _should_auto_reply(payload.role, context_tag):
            chat_context = build_chat_context(context_tag, session, payload)
            raw_contract = _call_local_llm_contract(payload.content.strip(), chat_context)
            contract, gate = parse_validate_and_gate(raw_contract, context=chat_context)
            llm_gate = gate
            reply_text = str(contract.get("text", "")).strip()
            reply_kind = str(contract.get("kind", "CLARIFY")).upper()
            reply_status = "pending" if reply_kind == "CLARIFY" else "normal"
            if reply_kind == "TASK_PLAN":
                task_plan_work_id = _enqueue_task_plan(
                    session,
                    contract=contract,
                    context_tag=context_tag,
                    linked_node=payload.linked_node,
                )
            reply_meta: dict[str, Any] = {
                "schema": contract.get("schema"),
                "kind": reply_kind,
                "needs": contract.get("needs"),
                "task_plan": contract.get("task_plan"),
                "sources": contract.get("sources"),
                "confidence_model": contract.get("confidence_model"),
                "gate_score": gate.get("gate_score"),
                "evidence_scope": gate.get("evidence_scope"),
                "gate_reason": gate.get("reason", ""),
                "fallback_applied": bool(gate.get("fallback_applied", False)),
            }
            if task_plan_work_id:
                reply_meta["work_package_id"] = task_plan_work_id
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
                content=payload.content.strip(),
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
                    snippet=payload.content.strip()[:200],
                    source=f"question.response:{payload.linked_cluster}",
                    evidence_timestamp=_to_iso(_utc_now()),
                    linked_node=payload.linked_node,
                )

            lowered = payload.content.strip().lower()
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
                dedup_key=f"question_response:{payload.linked_cluster}:{payload.content.strip()}",
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
            "reply_skipped": bool(payload.role == "user" and context_tag == "system"),
            "gate": llm_gate or {},
            "task_plan_work_id": task_plan_work_id,
            "learned_rule": learned_rule,
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
