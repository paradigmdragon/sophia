from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from api.config import settings
from api.sophia_notes import append_system_note
from core.memory.schema import MindItem, MindLearningRollup, MindWorkingLog, create_session_factory
from core.services.bitmap_audit_service import build_bitmap_audit_snapshot
from core.services.bitmap_summary_service import build_bitmap_summary
from sophia_kernel.modules.mind_diary import (
    adjust_mind_item,
    ingest_trigger_event,
    maybe_build_daily_diary,
    select_mind_dashboard,
)

router = APIRouter(prefix="/mind", tags=["mind"])
_SessionLocal = create_session_factory(settings.db_path)


def _get_db() -> Session:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


class MindAdjustPayload(BaseModel):
    label: str | None = None


class TriggerPayload(BaseModel):
    event_type: str
    payload: dict[str, Any] = {}


def _to_iso(value) -> str:
    if value is None:
        return ""
    return value.isoformat().replace("+00:00", "Z")


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


def _serialize_rollup(row: MindLearningRollup | None) -> dict[str, Any]:
    if row is None:
        return {}
    payload = row.payload if isinstance(row.payload, dict) else {}
    return {
        "rollup_type": row.rollup_type,
        "bucket_key": row.bucket_key,
        "payload": payload,
        "source_event_count": int(row.source_event_count or 0),
        "computed_at": _to_iso(row.computed_at),
    }


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        value = raw.strip()
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _parse_dt(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        value = raw.strip()
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _maybe_append_daily_diary(db: Session) -> dict[str, Any] | None:
    diary = maybe_build_daily_diary(db)
    if diary is None:
        return None
    result = append_system_note(
        db=db,
        note_type=str(diary["note_type"]),
        source_events=list(diary["source_events"]),
        summary=str(diary["summary"]),
        body_markdown=str(diary["body_markdown"]),
        status=str(diary["status"]),
        actionables=list(diary["actionables"]),
        badge=str(diary["badge"]),
        dedup_key=str(diary["dedup_key"]),
    )
    return result["note"]


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(_get_db)) -> dict[str, Any]:
    return select_mind_dashboard(db)


@router.get("/learning")
def get_learning_summary(db: Session = Depends(_get_db)) -> dict[str, Any]:
    total_row = (
        db.query(MindLearningRollup)
        .filter(
            MindLearningRollup.rollup_type == "TOTAL",
            MindLearningRollup.bucket_key == "all",
        )
        .one_or_none()
    )
    window_row = (
        db.query(MindLearningRollup)
        .filter(
            MindLearningRollup.rollup_type == "WINDOW_24H",
            MindLearningRollup.bucket_key == "rolling",
        )
        .one_or_none()
    )
    top_row = (
        db.query(MindLearningRollup)
        .filter(
            MindLearningRollup.rollup_type == "TOP_PATTERNS",
            MindLearningRollup.bucket_key == "rolling",
        )
        .one_or_none()
    )
    daily_rows = (
        db.query(MindLearningRollup)
        .filter(MindLearningRollup.rollup_type == "DAILY")
        .order_by(MindLearningRollup.bucket_key.desc())
        .limit(7)
        .all()
    )

    total_payload = total_row.payload if total_row is not None and isinstance(total_row.payload, dict) else {}
    window_payload = window_row.payload if window_row is not None and isinstance(window_row.payload, dict) else {}
    top_payload = top_row.payload if top_row is not None and isinstance(top_row.payload, dict) else {}

    return {
        "status": "ok",
        "growth_stage": str(total_payload.get("growth_stage", "SEED")),
        "total_tracked_events": int(total_payload.get("total_tracked_events", 0) or 0),
        "tracked_events": total_payload.get("tracked_events", {}),
        "unconscious_ratio": float(total_payload.get("unconscious_ratio", 0.0) or 0.0),
        "preference_stability": float(total_payload.get("preference_stability", 0.0) or 0.0),
        "topic_density": float(total_payload.get("topic_density", 0.0) or 0.0),
        "last_event_at": str(total_payload.get("last_event_at", "")),
        "tracked_events_24h": window_payload.get("tracked_events_24h", {}),
        "top_unconscious_patterns": top_payload.get("top_unconscious_patterns", []),
        "rollups": {
            "total": _serialize_rollup(total_row),
            "window_24h": _serialize_rollup(window_row),
            "top_patterns": _serialize_rollup(top_row),
            "daily": [_serialize_rollup(row) for row in daily_rows],
        },
    }


@router.get("/bitmap")
def get_bitmap_summary(days: int = Query(default=7, ge=1, le=30), db: Session = Depends(_get_db)) -> dict[str, Any]:
    summary = build_bitmap_summary(db, days=days, limit=10)
    return {"status": "ok", **summary}


@router.get("/bitmap/audit")
def get_bitmap_audit(
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    reason_limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    snapshot = build_bitmap_audit_snapshot(db, days=days, limit=limit, reason_limit=reason_limit)
    return {"status": "ok", **snapshot}


@router.get("/bitmap/candidates/{candidate_id}/timeline")
def get_bitmap_candidate_timeline(
    candidate_id: str,
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    bind = db.get_bind()
    if bind is None:
        raise HTTPException(status_code=500, detail="DB bind not available")

    inspector = sa_inspect(bind)
    if not inspector.has_table("candidates"):
        raise HTTPException(status_code=404, detail="candidates table not found")

    candidate_row = db.execute(
        text(
            """
            SELECT candidate_id, episode_id, note_thin, confidence, proposed_at, status
            FROM candidates
            WHERE candidate_id = :candidate_id
            LIMIT 1
            """
        ),
        {"candidate_id": candidate_id},
    ).fetchone()
    if candidate_row is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    event_columns = {column["name"] for column in inspector.get_columns("events")} if inspector.has_table("events") else set()
    if not event_columns:
        return {
            "status": "ok",
            "candidate": {
                "id": str(candidate_row[0]),
                "episode_id": str(candidate_row[1] or ""),
                "note": str(candidate_row[2] or ""),
                "confidence": int(candidate_row[3] or 0),
                "proposed_at": _to_iso(_parse_dt(candidate_row[4])),
                "status_value": str(candidate_row[5] or ""),
            },
            "events": [],
        }

    has_episode_col = "episode_id" in event_columns
    if has_episode_col:
        rows = db.execute(
            text(
                """
                SELECT event_id, type, payload, at, episode_id
                FROM events
                WHERE episode_id = :episode_id
                  AND type IN ('PROPOSE', 'ADOPT', 'REJECT', 'BITMAP_INVALID', 'CONFLICT_MARK', 'EPIDORA_MARK')
                ORDER BY at DESC
                LIMIT :limit
                """
            ),
            {"episode_id": str(candidate_row[1] or ""), "limit": max(int(limit) * 4, 200)},
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """
                SELECT event_id, type, payload, at, NULL AS episode_id
                FROM events
                ORDER BY at DESC
                LIMIT :limit
                """
            ),
            {"limit": max(int(limit) * 6, 300)},
        ).fetchall()

    now = datetime.now(UTC)
    candidate_episode_id = str(candidate_row[1] or "").strip()
    timeline: list[dict[str, Any]] = []
    for row in rows:
        event_type = str(row[1] or "").strip().upper()
        payload = _parse_payload(row[2])
        payload_candidate = str(payload.get("candidate_id", "")).strip()
        row_episode_id = str(row[4] or "").strip()
        when = _parse_dt(row[3])
        if when is None:
            continue
        if (now - when).days > int(days):
            continue
        same_candidate = payload_candidate == candidate_id
        same_episode = bool(candidate_episode_id and row_episode_id and row_episode_id == candidate_episode_id)
        candidate_level_event = event_type in {"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID"}
        episode_level_event = event_type in {"CONFLICT_MARK", "EPIDORA_MARK"}

        include_event = False
        if candidate_level_event and same_candidate:
            # Guard against legacy cross-episode contamination: keep same-candidate
            # events only when episode matches (or when episode column is absent).
            if not has_episode_col:
                include_event = True
            elif not candidate_episode_id or not row_episode_id:
                include_event = True
            else:
                include_event = row_episode_id == candidate_episode_id
        elif episode_level_event and same_episode:
            include_event = True

        if not include_event:
            continue
        summary = str(payload.get("summary", "")).strip()
        if not summary:
            if event_type == "REJECT":
                reason = str(payload.get("reason", "")).strip()
                summary = f"candidate rejected{f' ({reason})' if reason else ''}"
            elif event_type == "ADOPT":
                summary = f"candidate adopted ({payload.get('backbone_id', '-')})"
            elif event_type == "PROPOSE":
                summary = f"candidate proposed source={payload.get('source', '-')}"
            elif event_type == "BITMAP_INVALID":
                summary = f"bitmap invalid {payload.get('reason', 'INVALID_BITMAP')}"
            else:
                summary = event_type.lower()
        timeline.append(
            {
                "event_id": str(row[0] or ""),
                "event_type": event_type,
                "at": _to_iso(when),
                "episode_id": row_episode_id,
                "candidate_id": payload_candidate or candidate_id,
                "summary": summary,
                "payload": payload,
            }
        )
        if len(timeline) >= int(limit):
            break

    return {
        "status": "ok",
        "candidate": {
            "id": str(candidate_row[0]),
            "episode_id": str(candidate_row[1] or ""),
            "note": str(candidate_row[2] or ""),
            "confidence": int(candidate_row[3] or 0),
            "proposed_at": _to_iso(_parse_dt(candidate_row[4])),
            "status_value": str(candidate_row[5] or ""),
        },
        "events": timeline,
    }


@router.get("/items")
def list_items(
    status: str = Query(default="active"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    query = db.query(MindItem)
    if status != "all":
        query = query.filter(MindItem.status == status)
    rows = query.order_by(MindItem.priority.desc(), MindItem.updated_at.desc(), MindItem.id.asc()).limit(limit).all()
    return {"items": [_serialize_item(row) for row in rows]}


@router.get("/working-log")
def get_working_log(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(_get_db)) -> dict[str, Any]:
    rows = (
        db.query(MindWorkingLog)
        .order_by(MindWorkingLog.created_at.desc(), MindWorkingLog.id.desc())
        .limit(limit)
        .all()
    )
    lines = [
        {
            "id": row.id,
            "line": row.line,
            "event_type": row.event_type,
            "item_id": row.item_id,
            "delta_priority": int(row.delta_priority or 0),
        }
        for row in reversed(rows)
    ]
    return {"items": lines}


def _apply_action(
    *,
    item_id: str,
    action: Literal["pin", "boost", "park", "done", "label"],
    payload: MindAdjustPayload,
    db: Session,
) -> dict[str, Any]:
    try:
        item = adjust_mind_item(db, item_id=item_id, action=action, label=payload.label)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    diary = _maybe_append_daily_diary(db)
    db.commit()
    return {"status": "ok", "item": item, "daily_diary": diary}


@router.post("/items/{item_id}/pin")
def pin_item(item_id: str, db: Session = Depends(_get_db)) -> dict[str, Any]:
    return _apply_action(item_id=item_id, action="pin", payload=MindAdjustPayload(), db=db)


@router.post("/items/{item_id}/boost")
def boost_item(item_id: str, db: Session = Depends(_get_db)) -> dict[str, Any]:
    return _apply_action(item_id=item_id, action="boost", payload=MindAdjustPayload(), db=db)


@router.post("/items/{item_id}/park")
def park_item(item_id: str, db: Session = Depends(_get_db)) -> dict[str, Any]:
    return _apply_action(item_id=item_id, action="park", payload=MindAdjustPayload(), db=db)


@router.post("/items/{item_id}/done")
def done_item(item_id: str, db: Session = Depends(_get_db)) -> dict[str, Any]:
    return _apply_action(item_id=item_id, action="done", payload=MindAdjustPayload(), db=db)


@router.post("/items/{item_id}/label")
def label_item(item_id: str, payload: MindAdjustPayload, db: Session = Depends(_get_db)) -> dict[str, Any]:
    return _apply_action(item_id=item_id, action="label", payload=payload, db=db)


@router.post("/trigger")
def trigger_event(payload: TriggerPayload, db: Session = Depends(_get_db)) -> dict[str, Any]:
    items = ingest_trigger_event(db, event_type=payload.event_type, payload=payload.payload)
    diary = _maybe_append_daily_diary(db)
    db.commit()
    return {"status": "ok", "items_created_or_updated": len(items), "daily_diary": diary}
