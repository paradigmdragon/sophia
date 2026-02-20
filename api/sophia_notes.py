from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.memory.schema import Book, Chapter, QuestionPool, Verse, WorkPackage

DEFAULT_BOOK_TITLE = "Book of Beginnings"

NOTE_TITLES: dict[str, str] = {
    "GROVE_SUMMARY": "Grove 분석 요약",
    "WORK_REPORT_DIGEST": "IDE 보고 정리",
    "QUESTION_RESPONSE_DIGEST": "질문 응답 반영",
    "INACTIVITY_OBSERVATION": "무활동 7일 관찰",
    "SOPHIA_ACTIVITY_OBSERVATION": "무활동 관찰 기록",
    "DIARY_DAILY": "Sophia Daily Diary",
    "MANUAL_TRIGGER_NOTE": "수동 생성 기록",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_verse_content(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ensure_book(db: Session, title: str) -> Book:
    row = db.query(Book).filter(Book.title == title).one_or_none()
    if row is not None:
        return row
    row = Book(title=title)
    db.add(row)
    db.flush()
    return row


def _ensure_chapter(db: Session, book_id: int, title: str) -> Chapter:
    row = (
        db.query(Chapter)
        .filter(
            Chapter.book_id == book_id,
            Chapter.title == title,
        )
        .one_or_none()
    )
    if row is not None:
        return row
    row = Chapter(book_id=book_id, title=title)
    db.add(row)
    db.flush()
    return row


def _next_verse_number(db: Session, chapter_id: int) -> int:
    current = (
        db.query(func.max(Verse.verse_number))
        .filter(Verse.chapter_id == chapter_id)
        .scalar()
    )
    return int(current or 0) + 1


def _default_title(note_type: str) -> str:
    return NOTE_TITLES.get(note_type, "소피아 기록")


def _make_dedup_key(note_type: str, source_events: list[str], summary: str, explicit_key: str | None = None) -> str:
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    payload = {
        "note_type": note_type,
        "source_events": sorted(source_events),
        "summary": summary,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"note:{note_type}:{digest[:16]}"


def _serialize_system_note(verse: Verse, parsed: dict[str, Any]) -> dict[str, Any]:
    created_at = _to_iso(verse.created_at)
    source_events = parsed.get("source_events", [])
    if not isinstance(source_events, list):
        source_events = []
    actionables = parsed.get("actionables", [])
    if not isinstance(actionables, list):
        actionables = []
    return {
        "id": parsed.get("id") or f"note_{verse.id}",
        "verse_id": verse.id,
        "created_at": created_at,
        "title": parsed.get("title") or _default_title(str(parsed.get("note_type", ""))),
        "note_type": parsed.get("note_type", "UNKNOWN"),
        "source_events": source_events,
        "summary": parsed.get("summary", ""),
        "body_markdown": parsed.get("body_markdown", ""),
        "status": parsed.get("status", "ACTIVE"),
        "actionables": actionables,
        "linked_cluster_id": parsed.get("linked_cluster_id"),
        "risk_score": parsed.get("risk_score"),
        "dedup_key": parsed.get("dedup_key", ""),
        "badge": parsed.get("badge", "INFO"),
        "raw": parsed,
    }


def append_system_note(
    *,
    db: Session,
    note_type: str,
    source_events: list[str],
    summary: str,
    body_markdown: str,
    status: str = "ACTIVE",
    actionables: list[dict[str, Any]] | None = None,
    linked_cluster_id: str | None = None,
    risk_score: float | None = None,
    badge: str = "INFO",
    dedup_key: str | None = None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    actionables = actionables or []
    created = created_at or _utc_now()
    dedup = _make_dedup_key(note_type, source_events, summary, explicit_key=dedup_key)

    # Dedup by recent note payload key
    recent = (
        db.query(Verse)
        .order_by(Verse.created_at.desc(), Verse.id.desc())
        .limit(500)
        .all()
    )
    for verse in recent:
        parsed = _parse_verse_content(verse.content)
        if parsed.get("__namespace") != "notes":
            continue
        if not parsed.get("system_generated"):
            continue
        if parsed.get("dedup_key") == dedup:
            return {"created": False, "note": _serialize_system_note(verse, parsed)}

    book = _ensure_book(db, DEFAULT_BOOK_TITLE)
    chapter_title = f"Session {created.date().isoformat()}"
    chapter = _ensure_chapter(db, book.id, chapter_title)

    note_payload = {
        "__namespace": "notes",
        "v": "sophia_note_v1",
        "system_generated": True,
        "id": f"note_{note_type.lower()}_{int(created.timestamp())}",
        "title": _default_title(note_type),
        "note_type": note_type,
        "source_events": source_events,
        "summary": summary,
        "body_markdown": body_markdown,
        "status": status,
        "actionables": actionables,
        "linked_cluster_id": linked_cluster_id,
        "risk_score": risk_score,
        "badge": badge,
        "dedup_key": dedup,
    }
    verse = Verse(
        chapter_id=chapter.id,
        verse_number=_next_verse_number(db, chapter.id),
        content=json.dumps(note_payload, ensure_ascii=False),
        speaker="Sophia",
        perspective="Objective",
        is_constitution_active=False,
        created_at=created,
    )
    db.add(verse)
    db.flush()
    return {"created": True, "note": _serialize_system_note(verse, note_payload)}


def list_system_notes(
    *,
    db: Session,
    date: str | None = None,
    include_archived: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = db.query(Verse).order_by(Verse.created_at.desc(), Verse.id.desc())
    if date:
        query = query.filter(func.date(Verse.created_at) == date)
    verses = query.limit(max(limit * 4, limit)).all()

    rows: list[dict[str, Any]] = []
    for verse in verses:
        parsed = _parse_verse_content(verse.content)
        if parsed.get("__namespace") != "notes":
            continue
        if not parsed.get("system_generated", False):
            continue
        note_status = str(parsed.get("status", "ACTIVE")).upper()
        if not include_archived and note_status == "ARCHIVED":
            continue
        rows.append(_serialize_system_note(verse, parsed))
        if len(rows) >= limit:
            break
    return rows


def list_system_note_dates(*, db: Session, include_archived: bool = False, limit: int = 365) -> list[str]:
    verses = db.query(Verse).order_by(Verse.created_at.desc(), Verse.id.desc()).all()
    dates: list[str] = []
    seen: set[str] = set()
    for verse in verses:
        parsed = _parse_verse_content(verse.content)
        if parsed.get("__namespace") != "notes":
            continue
        if not parsed.get("system_generated", False):
            continue
        note_status = str(parsed.get("status", "ACTIVE")).upper()
        if not include_archived and note_status == "ARCHIVED":
            continue
        date_str = verse.created_at.date().isoformat()
        if date_str in seen:
            continue
        seen.add(date_str)
        dates.append(date_str)
        if len(dates) >= limit:
            break
    return dates


def get_generator_status(*, db: Session) -> dict[str, Any]:
    notes = list_system_notes(db=db, limit=1, include_archived=True)
    last_generated_at = notes[0]["created_at"] if notes else ""
    last_trigger = ""
    if notes:
        source_events = notes[0].get("source_events", [])
        if isinstance(source_events, list) and source_events:
            last_trigger = str(source_events[0])

    now = _utc_now()
    reasons: list[str] = []
    generator_status = "idle"
    last_error = ""

    seven_days_ago = now - timedelta(days=7)
    recent_work_reports = (
        db.query(WorkPackage)
        .filter(WorkPackage.updated_at >= seven_days_ago, WorkPackage.status.in_(["DONE", "BLOCKED", "FAILED"]))
        .count()
    )
    if recent_work_reports == 0:
        reasons.append("작업 리포트 없음")

    recent_question_signals = (
        db.query(QuestionPool)
        .filter(QuestionPool.last_triggered_at.isnot(None), QuestionPool.last_triggered_at >= seven_days_ago)
        .count()
    )
    if recent_work_reports == 0 and recent_question_signals == 0:
        reasons.append("최근 7일 트리거 없음")

    failed_work = (
        db.query(WorkPackage)
        .filter(WorkPackage.status == "FAILED")
        .order_by(WorkPackage.updated_at.desc(), WorkPackage.id.desc())
        .first()
    )
    if failed_work is not None and not notes:
        generator_status = "failed"
        last_error = "분석 실패 또는 리포트 실패 이후 노트 미생성"
        reasons.append("분석 실패(마지막 실패 로그)")

    return {
        "last_generated_at": last_generated_at,
        "generator_status": generator_status,
        "last_trigger": last_trigger,
        "empty_reasons": reasons,
        "last_error": last_error,
    }
