from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from core.memory.schema import ChatTimelineMessage, QuestionPool, Verse, WorkPackage
from sophia_kernel.modules.question_engine import build_inactivity_question

INACTIVITY_THRESHOLD_DAYS = 7
COOLDOWN_AFTER_TRIGGER_DAYS = 3
EVENT_TYPE = "USER_INACTIVITY_7D"
NOTE_TYPE = "SOPHIA_ACTIVITY_OBSERVATION"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_content(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _latest_activity_at(session) -> datetime | None:
    candidates: list[datetime] = []
    chat_last = session.query(ChatTimelineMessage.created_at).order_by(ChatTimelineMessage.created_at.desc()).first()
    if chat_last and chat_last[0]:
        candidates.append(chat_last[0])
    memory_last = session.query(Verse.created_at).order_by(Verse.created_at.desc()).first()
    if memory_last and memory_last[0]:
        candidates.append(memory_last[0])
    work_last = session.query(WorkPackage.updated_at).order_by(WorkPackage.updated_at.desc()).first()
    if work_last and work_last[0]:
        candidates.append(work_last[0])
    if not candidates:
        return None
    return max(candidates)


def _has_cooldown(session, now: datetime) -> tuple[bool, str]:
    verses = session.query(Verse).order_by(Verse.created_at.desc(), Verse.id.desc()).limit(200).all()
    latest_next: datetime | None = None
    for verse in verses:
        parsed = _parse_content(verse.content)
        if parsed.get("note_type") != NOTE_TYPE:
            continue
        next_cooldown_at = str(parsed.get("next_cooldown_at") or "")
        if not next_cooldown_at:
            continue
        try:
            dt = datetime.fromisoformat(next_cooldown_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dt = dt.astimezone(UTC)
            if latest_next is None or dt > latest_next:
                latest_next = dt
            if now < dt:
                return True, _to_iso(dt)
        except ValueError:
            continue
    return False, _to_iso(latest_next)


def _collect_conditions(session) -> dict[str, Any]:
    has_incomplete_work = (
        session.query(WorkPackage)
        .filter(WorkPackage.status != "DONE")
        .count()
        > 0
    )

    repeated = (
        session.query(QuestionPool)
        .filter(QuestionPool.hit_count >= 3)
        .order_by(QuestionPool.hit_count.desc(), QuestionPool.risk_score.desc())
        .first()
    )
    repeated_cluster = repeated is not None

    active_project = False
    verses = session.query(Verse).order_by(Verse.created_at.desc(), Verse.id.desc()).limit(200).all()
    for verse in verses:
        parsed = _parse_content(verse.content)
        note_type = str(parsed.get("note_type", "")).lower()
        status = str(parsed.get("status", "")).lower()
        if note_type in {"design", "idea", "project"} and status == "active":
            active_project = True
            break

    return {
        "has_incomplete_work": has_incomplete_work,
        "repeated_cluster": repeated_cluster,
        "cluster_id": repeated.cluster_id if repeated is not None else "",
        "active_project": active_project,
        "project_name": "진행 중 프로젝트",
    }


def run_inactivity_check(
    *,
    session_factory,
    write_event: Callable[[str, dict[str, Any]], None] | None = None,
    append_note: Callable[[dict[str, Any]], None] | None = None,
    now: datetime | None = None,
    threshold_days: int = INACTIVITY_THRESHOLD_DAYS,
    cooldown_days: int = COOLDOWN_AFTER_TRIGGER_DAYS,
) -> dict[str, Any]:
    current = now or _utc_now()
    session = session_factory()
    try:
        threshold_days = max(1, int(threshold_days))
        cooldown_days = max(1, int(cooldown_days))
        last_activity_at = _latest_activity_at(session)
        if last_activity_at is None:
            return {
                "triggered": False,
                "reason": "no_activity_history",
                "next_eligible_at": _to_iso(current),
            }
        if last_activity_at.tzinfo is None:
            last_activity_at = last_activity_at.replace(tzinfo=UTC)
        last_activity_at = last_activity_at.astimezone(UTC)

        inactive_delta = current - last_activity_at
        days_inactive = inactive_delta.total_seconds() / 86400.0
        threshold_at = last_activity_at + timedelta(days=threshold_days)
        if days_inactive < threshold_days:
            return {
                "triggered": False,
                "reason": "threshold_not_met",
                "days_inactive": round(days_inactive, 2),
                "last_activity_at": _to_iso(last_activity_at),
                "next_eligible_at": _to_iso(threshold_at),
            }

        in_cooldown, next_cooldown_at = _has_cooldown(session, current)
        if in_cooldown:
            return {
                "triggered": False,
                "reason": "cooldown_active",
                "days_inactive": round(days_inactive, 2),
                "last_activity_at": _to_iso(last_activity_at),
                "next_eligible_at": next_cooldown_at or _to_iso(current + timedelta(days=cooldown_days)),
            }

        conditions = _collect_conditions(session)
        condition_hit = (
            conditions["has_incomplete_work"]
            or conditions["repeated_cluster"]
            or conditions["active_project"]
        )
        if not condition_hit:
            return {
                "triggered": False,
                "reason": "no_justified_condition",
                "days_inactive": round(days_inactive, 2),
                "last_activity_at": _to_iso(last_activity_at),
                "next_eligible_at": _to_iso(current + timedelta(days=1)),
            }

        question = build_inactivity_question(conditions)
        event_payload = {
            "event_type": EVENT_TYPE,
            "last_activity_at": _to_iso(last_activity_at),
            "detected_at": _to_iso(current),
            "days_inactive": round(days_inactive, 2),
            "question_text": question["question_text"],
        }
        if write_event is not None:
            write_event(EVENT_TYPE, event_payload)

        note_payload = {
            "note_type": NOTE_TYPE,
            "inactivity_days": round(days_inactive, 2),
            "reason_detected": [k for k, v in conditions.items() if isinstance(v, bool) and v],
            "question_generated": question["question_text"],
            "next_cooldown_at": _to_iso(current + timedelta(days=cooldown_days)),
        }
        if append_note is not None:
            append_note(note_payload)

        return {
            "triggered": True,
            "event_type": EVENT_TYPE,
            "days_inactive": round(days_inactive, 2),
            "last_activity_at": _to_iso(last_activity_at),
            "question": question,
            "note": note_payload,
            "next_eligible_at": note_payload["next_cooldown_at"],
        }
    finally:
        session.close()
