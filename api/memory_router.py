from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config import settings
from api.sophia_notes import (
    append_system_note,
    get_generator_status,
    list_system_note_dates,
    list_system_notes,
)
from core.memory.schema import Book, Chapter, Verse, create_session_factory

router = APIRouter(prefix="/memory", tags=["memory"])
_SessionLocal = create_session_factory(settings.db_path)
DEFAULT_BOOK_TITLE = "Book of Beginnings"


def _get_db() -> Session:
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {"text": content}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _infer_namespace(parsed: dict[str, Any]) -> str:
    explicit = parsed.get("__namespace")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    kind = parsed.get("kind")
    if isinstance(kind, str) and kind in {
        "chat_message",
        "shell_command",
        "ide_log",
        "ide_worklog",
        "action",
    }:
        return "actions"

    if "title" in parsed or "body" in parsed or "tags" in parsed:
        return "notes"

    return "notes"


def _serialize_verse(verse: Verse) -> dict[str, Any]:
    parsed = _parse_content(verse.content)
    namespace = _infer_namespace(parsed)
    return {
        "id": verse.id,
        "chapter_id": verse.chapter_id,
        "verse_number": verse.verse_number,
        "speaker": verse.speaker,
        "perspective": verse.perspective,
        "is_constitution_active": verse.is_constitution_active,
        "created_at": _to_iso(verse.created_at),
        "content": verse.content,
        "parsed": parsed,
        "namespace": namespace,
    }


def _ensure_book(db: Session, title: str) -> Book:
    book = db.query(Book).filter(Book.title == title).one_or_none()
    if book:
        return book
    book = Book(title=title)
    db.add(book)
    db.flush()
    return book


def _ensure_chapter(db: Session, book_id: int, title: str) -> Chapter:
    chapter = (
        db.query(Chapter)
        .filter(
            Chapter.book_id == book_id,
            Chapter.title == title,
        )
        .one_or_none()
    )
    if chapter:
        return chapter
    chapter = Chapter(book_id=book_id, title=title)
    db.add(chapter)
    db.flush()
    return chapter


def _next_verse_number(db: Session, chapter_id: int) -> int:
    current = (
        db.query(func.max(Verse.verse_number))
        .filter(Verse.chapter_id == chapter_id)
        .scalar()
    )
    return int(current or 0) + 1


@router.get("/books")
def list_books(db: Session = Depends(_get_db)) -> list[dict[str, Any]]:
    rows = db.query(Book).order_by(Book.created_at.desc(), Book.id.desc()).all()
    return [
        {
            "id": row.id,
            "title": row.title,
            "created_at": _to_iso(row.created_at),
        }
        for row in rows
    ]


@router.get("/books/{book_id}")
def list_chapters_in_book(book_id: int, db: Session = Depends(_get_db)) -> list[dict[str, Any]]:
    book = db.query(Book).filter(Book.id == book_id).one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail=f"book not found: {book_id}")

    rows = (
        db.query(
            Chapter.id,
            Chapter.book_id,
            Chapter.title,
            Chapter.summary,
            func.count(Verse.id).label("verse_count"),
        )
        .outerjoin(Verse, Verse.chapter_id == Chapter.id)
        .filter(Chapter.book_id == book_id)
        .group_by(Chapter.id)
        .order_by(Chapter.id.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "book_id": row.book_id,
            "title": row.title,
            "summary": row.summary,
            "verse_count": int(row.verse_count or 0),
        }
        for row in rows
    ]


@router.get("/chapters/{chapter_id}")
def list_verses_in_chapter(chapter_id: int, db: Session = Depends(_get_db)) -> list[dict[str, Any]]:
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail=f"chapter not found: {chapter_id}")

    verses = (
        db.query(Verse)
        .filter(Verse.chapter_id == chapter_id)
        .order_by(Verse.verse_number.asc(), Verse.id.asc())
        .all()
    )
    return [_serialize_verse(verse) for verse in verses]


@router.get("/chapters")
def list_chapters_or_by_date(
    date: str | None = Query(default=None),
    namespace: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    if date is None:
        chapters = db.query(Chapter).order_by(Chapter.id.desc()).limit(limit).all()
        return {
            "items": [
                {
                    "id": chapter.id,
                    "book_id": chapter.book_id,
                    "title": chapter.title,
                    "summary": chapter.summary,
                }
                for chapter in chapters
            ]
        }

    chapter_title = f"Session {date}"
    verses = (
        db.query(Verse)
        .join(Chapter, Chapter.id == Verse.chapter_id)
        .filter(
            (Chapter.title == chapter_title) | (func.date(Verse.created_at) == date),
        )
        .order_by(Verse.created_at.asc(), Verse.verse_number.asc(), Verse.id.asc())
        .all()
    )

    items = [_serialize_verse(verse) for verse in verses]
    if namespace:
        items = [item for item in items if item["namespace"] == namespace]
    return {"date": date, "items": items[:limit]}


@router.get("/verses")
def list_verses(
    namespace: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    # Namespace is inferred from verse content, so fetch a larger window then filter.
    fetch_size = limit * 4 if namespace else limit
    verses = (
        db.query(Verse)
        .order_by(Verse.created_at.desc(), Verse.id.desc())
        .limit(fetch_size)
        .all()
    )
    items = [_serialize_verse(verse) for verse in verses]
    if namespace:
        items = [item for item in items if item["namespace"] == namespace]
    return {"items": items[:limit]}


@router.get("/dates")
def list_dates(
    namespace: str | None = Query(default=None),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    verses = db.query(Verse).order_by(Verse.created_at.desc(), Verse.id.desc()).all()
    dates: list[str] = []
    seen: set[str] = set()
    for verse in verses:
        item = _serialize_verse(verse)
        if namespace and item["namespace"] != namespace:
            continue
        dt = verse.created_at
        if dt is None:
            continue
        date_str = dt.date().isoformat()
        if date_str in seen:
            continue
        seen.add(date_str)
        dates.append(date_str)
    return {"dates": dates}


class CreateVerseRequest(BaseModel):
    chapter_id: int | None = None
    book_title: str = Field(default=DEFAULT_BOOK_TITLE, min_length=1, max_length=255)
    chapter_title: str | None = None
    date: str | None = None
    content: dict[str, Any] | str
    speaker: str = "User"
    perspective: str | None = None
    is_constitution_active: bool = False
    created_at: datetime | None = None
    namespace: str | None = None


class GenerateNoteNowRequest(BaseModel):
    reason: str | None = None


@router.post("/verse")
def create_verse(req: CreateVerseRequest, db: Session = Depends(_get_db)) -> dict[str, Any]:
    if req.created_at is not None:
        created_at = req.created_at
    elif req.date:
        try:
            created_at = datetime.fromisoformat(f"{req.date}T00:00:00+00:00")
        except ValueError:
            created_at = datetime.now(UTC)
    else:
        created_at = datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    created_at = created_at.astimezone(UTC)

    if req.chapter_id is not None:
        chapter = db.query(Chapter).filter(Chapter.id == req.chapter_id).one_or_none()
        if not chapter:
            raise HTTPException(status_code=404, detail=f"chapter not found: {req.chapter_id}")
    else:
        book = _ensure_book(db, req.book_title)
        date_str = req.date or created_at.date().isoformat()
        chapter_title = req.chapter_title or f"Session {date_str}"
        chapter = _ensure_chapter(db, book.id, chapter_title)

    payload: dict[str, Any]
    if isinstance(req.content, dict):
        payload = dict(req.content)
    else:
        payload = {"text": req.content}
    if req.namespace and "__namespace" not in payload:
        payload["__namespace"] = req.namespace

    verse = Verse(
        chapter_id=chapter.id,
        verse_number=_next_verse_number(db, chapter.id),
        content=json.dumps(payload, ensure_ascii=False),
        speaker=req.speaker,
        perspective=req.perspective,
        is_constitution_active=req.is_constitution_active,
        created_at=created_at,
    )
    db.add(verse)
    db.commit()
    db.refresh(verse)
    return _serialize_verse(verse)


@router.get("/notes")
def get_system_notes(
    date: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    system_generated_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    if not system_generated_only:
        # Keep compatibility path, but default stays system-generated only.
        items = list_chapters_or_by_date(date=date, namespace="notes", limit=limit, db=db).get("items", [])
        return {"items": items, "system_generated_only": False}

    notes = list_system_notes(db=db, date=date, include_archived=include_archived, limit=limit)
    return {"items": notes, "system_generated_only": True}


@router.get("/notes/dates")
def get_system_note_dates(
    include_archived: bool = Query(default=False),
    db: Session = Depends(_get_db),
) -> dict[str, Any]:
    return {"dates": list_system_note_dates(db=db, include_archived=include_archived)}


@router.get("/notes/status")
def get_notes_generator_status(db: Session = Depends(_get_db)) -> dict[str, Any]:
    return get_generator_status(db=db)


@router.post("/notes/generate")
def generate_note_now(req: GenerateNoteNowRequest, db: Session = Depends(_get_db)) -> dict[str, Any]:
    reason = (req.reason or "manual refresh").strip()
    result = append_system_note(
        db=db,
        note_type="MANUAL_TRIGGER_NOTE",
        source_events=["MANUAL_TRIGGER"],
        summary="수동 생성 트리거로 노트를 갱신했습니다.",
        body_markdown=f"- trigger: {reason}\n- generated_at: {datetime.now(UTC).isoformat().replace('+00:00', 'Z')}",
        status="ACTIVE",
        badge="INFO",
        dedup_key=f"manual:{datetime.now(UTC).date().isoformat()}:{reason}",
    )
    db.commit()
    return {"status": "ok", "created": result["created"], "item": result["note"]}
