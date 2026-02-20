from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func

from core.services.learning_rollup_service import update_learning_rollup_on_event
from core.memory.schema import MindItem, MindWorkingLog, Verse

MAX_WORKING_LOG_LINES = 50
MAX_LINE_CHARS = 80

CORE_DICTIONARY_TAGS = ["sone", "sona", "logos64", "epidora"]
ALLOWED_LABELS = {
    "sone",
    "sona",
    "logos64",
    "epidora",
    "hanja",
    "ethics",
    "design",
    "project",
    "analysis",
    "risk",
    "question",
    "work",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _summary_120(text: str) -> str:
    clean = " ".join((text or "").split())
    return clean[:120]


def _line_80(text: str) -> str:
    return _summary_120(text)[:MAX_LINE_CHARS]


def _merge_unique(items: list[str], extra: list[str]) -> list[str]:
    out = [item for item in items if isinstance(item, str) and item.strip()]
    for value in extra:
        v = str(value).strip()
        if not v or v in out:
            continue
        out.append(v)
    return out


def _extract_missing_slots_count(payload: dict[str, Any]) -> int:
    if "missing_slots" in payload and isinstance(payload["missing_slots"], int):
        return max(0, payload["missing_slots"])
    # fallback signal count
    if "signals" in payload and isinstance(payload["signals"], int):
        return max(0, payload["signals"])
    return 0


def _calc_priority(
    *,
    recency_score: float,
    frequency_score: float,
    risk_score: float,
    grove_dependency_score: float,
) -> int:
    w1, w2, w3, w4 = 0.35, 0.2, 0.25, 0.2
    priority = (
        w1 * recency_score
        + w2 * frequency_score
        + w3 * (risk_score * 100.0)
        + w4 * grove_dependency_score
    )
    return int(round(_clamp(priority, 0.0, 100.0)))


def _bounded_priority(previous: int, candidate: int) -> int:
    if candidate > previous + 20:
        return previous + 20
    if candidate < previous - 20:
        return previous - 20
    return int(_clamp(candidate, 0, 100))


def _append_working_log(session, *, event_type: str, item_id: str | None, line: str, delta_priority: int = 0) -> None:
    row = MindWorkingLog(
        line=_line_80(line),
        event_type=event_type,
        item_id=item_id,
        delta_priority=int(delta_priority),
        created_at=_utc_now(),
    )
    session.add(row)
    session.flush()

    stale = (
        session.query(MindWorkingLog)
        .order_by(MindWorkingLog.created_at.desc(), MindWorkingLog.id.desc())
        .offset(MAX_WORKING_LOG_LINES)
        .all()
    )
    for old in stale:
        session.delete(old)


def _extract_focus_tags(payload: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    text_blob = json.dumps(payload, ensure_ascii=False).lower()
    for base in CORE_DICTIONARY_TAGS:
        if base in text_blob:
            tags.append(base)
    if "hanja" in text_blob:
        tags.append("hanja")
    if "ethics" in text_blob:
        tags.append("ethics")
    return tags


def _extract_mapping_hint(summary: str) -> str:
    quoted = re.findall(r"'([^']+)'", summary or "")
    if len(quoted) >= 2:
        return quoted[1][:60]
    clean = _summary_120(summary or "")
    return clean[:60]


def _tokenize_text(text: str) -> set[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣_:-]+", (text or "").lower())
    return {token for token in tokens if len(token) >= 2}


def mind_query_for_chat(
    session,
    *,
    user_text: str,
    context_tag: str,
    max_hits: int = 5,
    topic_recent_days: int = 14,
) -> dict[str, Any]:
    lowered = (user_text or "").strip().lower()
    tokens = _tokenize_text(lowered)
    now = _utc_now()

    memory_hits: list[str] = []
    memory_notes: list[str] = []
    tone_hint = ""

    def add_hit(item_id: str, note: str = "") -> None:
        if not item_id or item_id in memory_hits or len(memory_hits) >= max_hits:
            return
        memory_hits.append(item_id)
        if note and note not in memory_notes and len(memory_notes) < 3:
            memory_notes.append(_summary_120(note))

    term_rows = (
        session.query(MindItem)
        .filter(
            MindItem.status == "active",
            MindItem.id.like("term:%"),
        )
        .order_by(MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(30)
        .all()
    )
    for row in term_rows:
        key = str(row.id).split(":", 1)[1].strip().lower() if ":" in str(row.id) else ""
        if not key:
            continue
        if key in lowered or key in tokens:
            meaning = _extract_mapping_hint(str(row.summary_120 or ""))
            add_hit(row.id, f"이전에 '{key}'를 '{meaning}'로 정리해 두셨어요.")

    preference_rows = (
        session.query(MindItem)
        .filter(
            MindItem.status == "active",
            MindItem.id.like("preference:%"),
        )
        .order_by(MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(10)
        .all()
    )
    for row in preference_rows:
        key = str(row.id).split(":", 1)[1].strip().lower() if ":" in str(row.id) else ""
        add_hit(row.id)
        if key == "response_tone":
            tone_hint = str(row.summary_120 or "")

    topic_rows = (
        session.query(MindItem)
        .filter(
            MindItem.status == "active",
            MindItem.id.like("topic:%"),
        )
        .order_by(MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(20)
        .all()
    )
    for row in topic_rows:
        updated_at = row.updated_at or row.created_at or now
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        else:
            updated_at = updated_at.astimezone(UTC)
        age_days = max((now - updated_at).total_seconds() / 86400.0, 0.0)
        if age_days > float(topic_recent_days):
            continue
        topic = str(row.id).split(":", 1)[1].strip().lower() if ":" in str(row.id) else ""
        if not topic:
            continue
        if topic in lowered or topic in tokens:
            add_hit(row.id, f"최근 '{topic}' 주제를 반복해서 다루고 계셨어요.")

    focus_rows = (
        session.query(MindItem)
        .filter(
            MindItem.status == "active",
            MindItem.type.in_(["FOCUS", "ALERT"]),
            MindItem.priority >= 90,
        )
        .order_by(MindItem.priority.desc(), MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(10)
        .all()
    )
    for row in focus_rows:
        if str(row.id).startswith(("term:", "preference:", "topic:")):
            continue
        add_hit(row.id, f"우선순위가 높은 항목은 '{_summary_120(str(row.title or ''))}'입니다.")
        break

    return {
        "context_tag": context_tag,
        "memory_hits": memory_hits[:max_hits],
        "memory_notes": memory_notes[:2],
        "tone_hint": tone_hint[:120],
        "memory_used": bool(memory_hits),
    }


def _serialize_item(row: MindItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "summary_120": row.summary_120,
        "priority": int(row.priority or 0),
        "risk_score": float(row.risk_score or 0.0),
        "confidence": float(row.confidence or 0.0),
        "linked_bits": row.linked_bits or [],
        "tags": row.tags or [],
        "source_events": row.source_events or [],
        "status": row.status,
        "created_at": _to_iso(row.created_at),
        "updated_at": _to_iso(row.updated_at),
    }


def _parse_verse_content(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _upsert_mind_item(
    session,
    *,
    item_id: str,
    item_type: str,
    title: str,
    summary: str,
    source_event: str,
    linked_bits: list[str] | None = None,
    tags: list[str] | None = None,
    risk_score: float = 0.0,
    confidence: float = 0.6,
    grove_dependency_score: float = 0.0,
) -> MindItem:
    linked_bits = linked_bits or []
    tags = tags or []
    now = _utc_now()
    row = session.query(MindItem).filter(MindItem.id == item_id).one_or_none()

    if row is None:
        recency_score = 100.0
        frequency_score = 30.0
        candidate = _calc_priority(
            recency_score=recency_score,
            frequency_score=frequency_score,
            risk_score=risk_score,
            grove_dependency_score=grove_dependency_score,
        )
        row = MindItem(
            id=item_id,
            type=item_type,
            title=title,
            summary_120=_summary_120(summary),
            priority=candidate,
            risk_score=float(_clamp(risk_score, 0.0, 1.0)),
            confidence=float(_clamp(confidence, 0.0, 1.0)),
            linked_bits=linked_bits,
            tags=_merge_unique(tags, []),
            source_events=[source_event],
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        _append_working_log(
            session,
            event_type=source_event,
            item_id=row.id,
            line=f"[{now.strftime('%H:%M')}] {item_type} 생성",
            delta_priority=int(row.priority or 0),
        )
        return row

    previous = int(row.priority or 0)
    source_events = list(row.source_events or [])
    if source_event not in source_events:
        source_events.append(source_event)
    frequency_score = min(float(len(source_events) * 10), 100.0)

    updated_at = row.updated_at or row.created_at or now
    if isinstance(updated_at, datetime):
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        else:
            updated_at = updated_at.astimezone(UTC)
    age_hours = max((now - updated_at).total_seconds() / 3600.0, 0.0)
    recency_score = float(_clamp(100.0 - age_hours * 4.0, 0.0, 100.0))

    candidate = _calc_priority(
        recency_score=recency_score,
        frequency_score=frequency_score,
        risk_score=max(float(row.risk_score or 0.0), float(risk_score)),
        grove_dependency_score=grove_dependency_score,
    )
    bounded = _bounded_priority(previous, candidate)
    row.priority = bounded
    row.title = title
    row.summary_120 = _summary_120(summary)
    row.risk_score = float(_clamp(max(float(row.risk_score or 0.0), risk_score), 0.0, 1.0))
    row.confidence = float(_clamp(max(float(row.confidence or 0.0), confidence), 0.0, 1.0))
    row.linked_bits = _merge_unique(list(row.linked_bits or []), linked_bits)
    row.tags = _merge_unique(list(row.tags or []), tags)
    row.source_events = source_events
    if row.status not in {"active", "parked", "done"}:
        row.status = "active"
    row.updated_at = now
    session.add(row)
    session.flush()

    delta = bounded - previous
    if delta != 0:
        _append_working_log(
            session,
            event_type=source_event,
            item_id=row.id,
            line=f"[{now.strftime('%H:%M')}] priority {delta:+d}",
            delta_priority=delta,
        )
    return row


def ingest_trigger_event(session, *, event_type: str, payload: dict[str, Any]) -> list[MindItem]:
    created_or_updated: list[MindItem] = []
    now = _utc_now()

    if event_type == "WORK_PACKAGE_CREATED":
        work_id = str(payload.get("id") or payload.get("work_package_id") or "").strip()
        if work_id:
            item = _upsert_mind_item(
                session,
                item_id=f"task:{work_id}",
                item_type="TASK",
                title=f"Work {work_id}",
                summary=f"새 Work Package가 생성되었습니다 ({payload.get('kind', 'TASK')}).",
                source_event=event_type,
                linked_bits=[str(payload.get("context_tag") or "work")],
                tags=["work", * _extract_focus_tags(payload)],
                risk_score=0.0,
                confidence=0.75,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 작업 패킷 생성 감지",
            )

    elif event_type in {"GROVE_ANALYZED", "FOREST_ANALYSIS"}:
        missing_slots = _extract_missing_slots_count(payload)
        if missing_slots >= 1:
            target = str(payload.get("target") or payload.get("id") or "analysis").strip()
            item = _upsert_mind_item(
                session,
                item_id=f"alert:{target}",
                item_type="ALERT",
                title=f"분석 경고 {target}",
                summary=f"Grove 분석에서 누락/리스크 신호가 감지되었습니다 ({missing_slots}).",
                source_event="GROVE_ANALYZED",
                linked_bits=[target],
                tags=["analysis", "risk", *_extract_focus_tags(payload)],
                risk_score=float(_clamp(float(payload.get("risk_score", 0.7)), 0.0, 1.0)),
                confidence=0.8,
                grove_dependency_score=min(missing_slots * 20.0, 100.0),
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type="GROVE_ANALYZED",
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] grove 의존성 감지",
            )

    elif event_type == "QUESTION_READY":
        cluster_id = str(payload.get("cluster_id") or "").strip()
        if cluster_id:
            risk = float(payload.get("risk_score", 0.0))
            item = _upsert_mind_item(
                session,
                item_id=f"question:{cluster_id}",
                item_type="QUESTION_CLUSTER",
                title=f"질문 누적 {cluster_id}",
                summary=f"질문 클러스터가 발화 준비 상태입니다 (hit={payload.get('hit_count', 0)}).",
                source_event=event_type,
                linked_bits=[cluster_id],
                tags=["question", *_extract_focus_tags(payload)],
                risk_score=risk,
                confidence=0.7,
                grove_dependency_score=min(risk * 100.0, 100.0),
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 질문 클러스터 준비",
            )

    elif event_type == "USER_DOC_SAVED":
        doc = str(payload.get("target") or payload.get("doc_name") or "document").strip()
        item = _upsert_mind_item(
            session,
            item_id=f"focus:{doc}",
            item_type="FOCUS",
            title=f"집중 후보 {doc}",
            summary="사용자 문서 저장 이벤트 기반 집중 후보가 갱신되었습니다.",
            source_event=event_type,
            linked_bits=[doc],
            tags=["design", *_extract_focus_tags(payload)],
            risk_score=0.0,
            confidence=0.6,
            grove_dependency_score=0.0,
        )
        created_or_updated.append(item)
        _append_working_log(
            session,
            event_type=event_type,
            item_id=item.id,
            line=f"[{now.strftime('%H:%M')}] 사용자 문서 분석",
        )

    elif event_type == "USER_INACTIVITY_7D":
        cluster_id = str(payload.get("cluster_id") or "").strip()
        inactivity_days = float(payload.get("days_inactive", 7.0) or 7.0)
        template_id = str(payload.get("template_id") or "C")
        if cluster_id:
            item = _upsert_mind_item(
                session,
                item_id=f"question:{cluster_id}",
                item_type="QUESTION_CLUSTER",
                title=f"무활동 질문 {cluster_id}",
                summary=f"무활동 {inactivity_days:.1f}일 감지로 질문 클러스터가 생성되었습니다.",
                source_event=event_type,
                linked_bits=[cluster_id],
                tags=["question", "risk"],
                risk_score=float(_clamp(float(payload.get("risk_score", 0.7)), 0.0, 1.0)),
                confidence=0.72,
                grove_dependency_score=40.0,
            )
        else:
            item = _upsert_mind_item(
                session,
                item_id=f"alert:inactivity:{template_id}",
                item_type="ALERT",
                title="무활동 감지 알림",
                summary=f"무활동 {inactivity_days:.1f}일 상태에서 1회 개입이 필요합니다.",
                source_event=event_type,
                linked_bits=["inactivity"],
                tags=["risk"],
                risk_score=float(_clamp(float(payload.get("risk_score", 0.7)), 0.0, 1.0)),
                confidence=0.7,
                grove_dependency_score=30.0,
            )
        created_or_updated.append(item)
        _append_working_log(
            session,
            event_type=event_type,
            item_id=item.id,
            line=f"[{now.strftime('%H:%M')}] 무활동 이벤트 감지",
        )

    elif event_type == "TERM_MAPPING":
        term = str(payload.get("term") or "").strip()
        meaning = str(payload.get("meaning") or "").strip()
        if term and meaning:
            confidence = float(_clamp(float(payload.get("confidence", 0.7)), 0.0, 1.0))
            item = _upsert_mind_item(
                session,
                item_id=f"term:{term.lower()}",
                item_type="FOCUS",
                title=f"용어 매핑 {term}",
                summary=f"'{term}'은(는) '{meaning}' 의미로 학습되었습니다.",
                source_event=event_type,
                linked_bits=[f"term:{term.lower()}"],
                tags=["analysis", "term", *_extract_focus_tags(payload)],
                risk_score=0.0,
                confidence=confidence,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 용어 매핑 학습",
            )

    elif event_type == "TOPIC_SEEN":
        topic = str(payload.get("topic") or "").strip()
        count = int(payload.get("count", 0) or 0)
        if topic:
            item = _upsert_mind_item(
                session,
                item_id=f"topic:{topic.lower()}",
                item_type="FOCUS",
                title=f"반복 주제 {topic}",
                summary=f"최근 대화에서 '{topic}' 주제가 {max(count, 1)}회 관찰되었습니다.",
                source_event=event_type,
                linked_bits=[f"topic:{topic.lower()}"],
                tags=["analysis", "topic", *_extract_focus_tags(payload)],
                risk_score=0.0,
                confidence=0.65,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 반복 주제 감지",
            )

    elif event_type == "USER_PREFERENCE":
        key = str(payload.get("key") or "").strip().lower()
        value = str(payload.get("value") or "").strip()
        if key and value:
            confidence = float(_clamp(float(payload.get("confidence", 0.6)), 0.0, 1.0))
            item = _upsert_mind_item(
                session,
                item_id=f"preference:{key}",
                item_type="FOCUS",
                title=f"사용자 선호 {key}",
                summary=f"사용자 선호가 갱신되었습니다: {value[:80]}",
                source_event=event_type,
                linked_bits=[f"preference:{key}"],
                tags=["analysis", "preference", *_extract_focus_tags(payload)],
                risk_score=0.0,
                confidence=confidence,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 사용자 선호 갱신",
            )

    elif event_type == "UNCONSCIOUS_HIT":
        pattern_id = str(payload.get("pattern_id") or "").strip().upper()
        if pattern_id:
            confidence = float(_clamp(float(payload.get("confidence", 0.55)), 0.0, 1.0))
            summary = str(payload.get("summary") or "").strip()
            if not summary:
                summary = f"무의식 패턴 {pattern_id}가 반응 경로로 사용되었습니다."
            item = _upsert_mind_item(
                session,
                item_id=f"unconscious:hit:{pattern_id.lower()}",
                item_type="FOCUS",
                title=f"무의식 패턴 {pattern_id}",
                summary=summary,
                source_event=event_type,
                linked_bits=[f"unconscious:{pattern_id.lower()}"],
                tags=["analysis", "unconscious", pattern_id.lower()],
                risk_score=0.0,
                confidence=confidence,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 무의식 패턴 반응",
            )

    elif event_type == "UNCONSCIOUS_PATTERN_SEEN":
        pattern_id = str(payload.get("pattern_id") or "").strip().upper()
        day = str(payload.get("day") or now.date().isoformat()).strip()
        count = int(payload.get("count", 1) or 1)
        if pattern_id:
            item = _upsert_mind_item(
                session,
                item_id=f"unconscious:pattern:{day}:{pattern_id.lower()}",
                item_type="FOCUS",
                title=f"{day} 패턴 {pattern_id}",
                summary=f"{day} 기준으로 {pattern_id} 패턴이 {max(count, 1)}회 관찰되었습니다.",
                source_event=f"{event_type}:{day}",
                linked_bits=[f"unconscious:{pattern_id.lower()}"],
                tags=["analysis", "unconscious", "daily", pattern_id.lower()],
                risk_score=0.0,
                confidence=0.6,
                grove_dependency_score=0.0,
            )
            created_or_updated.append(item)
            _append_working_log(
                session,
                event_type=event_type,
                item_id=item.id,
                line=f"[{now.strftime('%H:%M')}] 무의식 패턴 일별 집계",
            )

    trace_id = str(payload.get("trace_id", "") or "").strip()
    update_learning_rollup_on_event(
        session,
        event_type=event_type,
        payload=payload,
        trace_id=trace_id or None,
    )
    return created_or_updated


def select_mind_dashboard(session, *, limit: int = 50) -> dict[str, Any]:
    rows = (
        session.query(MindItem)
        .order_by(MindItem.priority.desc(), MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(limit)
        .all()
    )
    items = [_serialize_item(row) for row in rows]
    focus_items = [item for item in items if item["type"] == "FOCUS" and item["status"] == "active"][:10]
    question_clusters = [item for item in items if item["type"] == "QUESTION_CLUSTER" and item["status"] == "active"][:10]
    risk_alerts = [item for item in items if item["type"] == "ALERT" and item["status"] == "active"][:10]

    logs = (
        session.query(MindWorkingLog)
        .order_by(MindWorkingLog.created_at.desc(), MindWorkingLog.id.desc())
        .limit(MAX_WORKING_LOG_LINES)
        .all()
    )
    log_rows = [
        {
            "id": row.id,
            "line": row.line,
            "event_type": row.event_type,
            "item_id": row.item_id,
            "delta_priority": int(row.delta_priority or 0),
            "created_at": _to_iso(row.created_at),
        }
        for row in reversed(logs)
    ]

    tag_counts: dict[str, int] = {}
    for item in items:
        if item["status"] != "active":
            continue
        for tag in item.get("tags", []):
            key = str(tag).strip().lower()
            if not key:
                continue
            tag_counts[key] = tag_counts.get(key, 0) + 1
    active_tags = [tag for tag, _ in sorted(tag_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:20]]

    return {
        "focus_items": focus_items,
        "question_clusters": question_clusters,
        "risk_alerts": risk_alerts,
        "working_log": log_rows,
        "active_tags": active_tags,
        "items": items,
    }


def adjust_mind_item(
    session,
    *,
    item_id: str,
    action: str,
    label: str | None = None,
) -> dict[str, Any]:
    row = session.query(MindItem).filter(MindItem.id == item_id).one_or_none()
    if row is None:
        raise KeyError(f"mind item not found: {item_id}")

    now = _utc_now()
    delta = 0
    if action == "pin":
        delta = max(0, 100 - int(row.priority or 0))
        row.priority = 100
        row.status = "active"
    elif action == "boost":
        previous = int(row.priority or 0)
        row.priority = min(100, previous + 10)
        delta = int(row.priority or 0) - previous
        row.status = "active"
    elif action == "park":
        row.status = "parked"
    elif action == "done":
        row.status = "done"
    elif action == "label":
        value = str(label or "").strip().lower()
        if value not in ALLOWED_LABELS:
            raise ValueError(f"label not allowed: {value}")
        row.tags = _merge_unique(list(row.tags or []), [value])
    else:
        raise ValueError(f"unsupported action: {action}")

    row.updated_at = now
    session.add(row)
    session.flush()
    _append_working_log(
        session,
        event_type=f"MIND_{action.upper()}",
        item_id=row.id,
        line=f"[{now.strftime('%H:%M')}] {action} 적용",
        delta_priority=delta,
    )
    return _serialize_item(row)


def maybe_build_daily_diary(session) -> dict[str, Any] | None:
    now = _utc_now()
    date_str = now.date().isoformat()
    chapter_title = f"Session {date_str}"
    day_verses = (
        session.query(Verse)
        .filter(func.date(Verse.created_at) == date_str)
        .order_by(Verse.created_at.desc(), Verse.id.desc())
        .all()
    )

    for verse in day_verses:
        parsed = _parse_verse_content(verse.content)
        if parsed.get("__namespace") == "notes" and parsed.get("note_type") == "DIARY_DAILY":
            return None

    logs_today = (
        session.query(MindWorkingLog)
        .filter(func.date(MindWorkingLog.created_at) == date_str)
        .order_by(MindWorkingLog.created_at.asc(), MindWorkingLog.id.asc())
        .all()
    )
    if not logs_today:
        return None

    event_count = len(logs_today)
    priority_delta_sum = sum(abs(int(row.delta_priority or 0)) for row in logs_today)
    if event_count < 1:
        return None

    active_items = (
        session.query(MindItem)
        .filter(MindItem.status == "active")
        .order_by(MindItem.priority.desc(), MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(3)
        .all()
    )
    top_titles = [row.title for row in active_items]
    observation = " / ".join(top_titles) if top_titles else "주요 항목 없음"

    summary = "오늘의 자동 관찰이 생성되었습니다."
    body = "\n".join(
        [
            "오늘의 관찰:",
            f"- {observation}",
            "",
            "정리된 방향:",
            f"- 이벤트 {event_count}건, priority 변동합 {priority_delta_sum}",
            "",
            "제안:",
            "- 활성 항목 우선순위 상위 1~3개를 검토하세요.",
        ]
    )
    return {
        "note_type": "DIARY_DAILY",
        "source_events": ["MIND_DAILY"],
        "summary": summary,
        "body_markdown": body,
        "status": "ACTIVE",
        "actionables": [{"type": "review_mind_dashboard"}],
        "badge": "INFO",
        "dedup_key": f"diary:{chapter_title}",
    }
