from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.memory.schema import Book, Chapter, Verse, create_session_factory

DEFAULT_DB_PATH = os.getenv("SOPHIA_DB_PATH", "sqlite:///sophia.db")
DEFAULT_BOOK_TITLE = "Book of Beginnings"
PRIMARY_NOTES_PATH = REPO_ROOT / "apps/desktop/src-tauri/data/memory/notes.jsonl"
PRIMARY_CHAT_PATH = REPO_ROOT / "apps/desktop/src-tauri/data/chat_memory.jsonl"
FALLBACK_NOTES_PATH = REPO_ROOT / "sophia_workspace/memory/notes.jsonl"
FALLBACK_CHAT_PATH = REPO_ROOT / "sophia_workspace/memory/actions.jsonl"


@dataclass
class SourceEntry:
    source: str
    line_no: int
    created_at: datetime
    speaker: str
    perspective: str | None
    is_constitution_active: bool
    content: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_source(primary: Path, fallback: Path) -> Path | None:
    if primary.exists():
        return primary
    if fallback.exists():
        return fallback
    return None


def _speaker_from_value(value: str | None) -> str:
    if not value:
        return "Unknown"
    lowered = value.strip().lower()
    if lowered == "user":
        return "User"
    if lowered in {"assistant", "sophia"}:
        return "Sophia"
    return value.strip()


def _extract_created_at(raw: dict, data: dict | None) -> datetime:
    candidates: list[str | None] = [
        raw.get("ts"),
        raw.get("timestamp"),
        raw.get("created_at"),
    ]
    timestamps = raw.get("timestamps")
    if isinstance(timestamps, dict):
        candidates.extend([timestamps.get("created_at"), timestamps.get("finished_at")])

    if data:
        candidates.extend(
            [
                data.get("ts"),
                data.get("timestamp"),
                data.get("created_at"),
            ]
        )

    for candidate in candidates:
        parsed = _iso_to_dt(candidate)
        if parsed:
            return parsed
    return _utc_now()


def _extract_content(raw_line: str, raw: dict, namespace: str) -> tuple[str, dict]:
    if isinstance(raw.get("data"), dict):
        payload = dict(raw["data"])
    else:
        payload = dict(raw)

    payload.setdefault("__namespace", namespace)
    if not payload:
        payload = {"text": raw_line, "__namespace": namespace}
    return json.dumps(payload, ensure_ascii=False), payload


def _extract_perspective(raw: dict, data: dict | None) -> str | None:
    for source in (raw, data or {}):
        perspective = source.get("perspective")
        if isinstance(perspective, str) and perspective.strip():
            return perspective.strip()
    return None


def _extract_constitution_flag(raw: dict, data: dict | None) -> bool:
    for source in (raw, data or {}):
        flag = source.get("is_constitution_active")
        if isinstance(flag, bool):
            return flag
    return False


def _extract_speaker(raw: dict, data: dict | None) -> str:
    for source in (raw, data or {}):
        for key in ("speaker", "role"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return _speaker_from_value(value)
    return "Unknown"


def _read_source(path: Path, namespace: str) -> Iterable[SourceEntry]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            raw_line = line.strip()
            if not raw_line:
                continue
            try:
                parsed = json.loads(raw_line)
            except json.JSONDecodeError:
                content = json.dumps({"text": raw_line, "__namespace": namespace}, ensure_ascii=False)
                yield SourceEntry(
                    source=namespace,
                    line_no=line_no,
                    created_at=_utc_now(),
                    speaker="Unknown",
                    perspective=None,
                    is_constitution_active=False,
                    content=content,
                )
                continue

            if not isinstance(parsed, dict):
                content = json.dumps({"text": raw_line, "__namespace": namespace}, ensure_ascii=False)
                yield SourceEntry(
                    source=namespace,
                    line_no=line_no,
                    created_at=_utc_now(),
                    speaker="Unknown",
                    perspective=None,
                    is_constitution_active=False,
                    content=content,
                )
                continue

            data = parsed.get("data") if isinstance(parsed.get("data"), dict) else None
            content, payload = _extract_content(raw_line=raw_line, raw=parsed, namespace=namespace)
            created_at = _extract_created_at(parsed, data)
            speaker = _extract_speaker(parsed, payload if isinstance(payload, dict) else data)
            perspective = _extract_perspective(parsed, data)
            is_constitution_active = _extract_constitution_flag(parsed, data)

            yield SourceEntry(
                source=namespace,
                line_no=line_no,
                created_at=created_at,
                speaker=speaker,
                perspective=perspective,
                is_constitution_active=is_constitution_active,
                content=content,
            )


def _entry_hash(entry: SourceEntry) -> str:
    canonical_created_at = _canonical_dt(entry.created_at)
    payload = (
        f"{canonical_created_at}|{entry.speaker}|{entry.perspective}|"
        f"{int(entry.is_constitution_active)}|{entry.content}"
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _canonical_dt(value: datetime) -> str:
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def migrate_memory(
    db_path: str = DEFAULT_DB_PATH,
    book_title: str = DEFAULT_BOOK_TITLE,
    notes_path: Path | None = None,
    chat_path: Path | None = None,
) -> dict:
    resolved_notes = notes_path or _resolve_source(PRIMARY_NOTES_PATH, FALLBACK_NOTES_PATH)
    resolved_chat = chat_path or _resolve_source(PRIMARY_CHAT_PATH, FALLBACK_CHAT_PATH)
    sources: list[tuple[Path, str]] = []
    if resolved_notes:
        sources.append((resolved_notes, "notes"))
    if resolved_chat:
        sources.append((resolved_chat, "actions"))

    if not sources:
        return {
            "status": "no_sources",
            "db_path": db_path,
            "book_title": book_title,
            "sources": [],
            "chapters_created": 0,
            "verses_created": 0,
            "verses_skipped_duplicate": 0,
        }

    session_factory = create_session_factory(db_path=db_path)
    session = session_factory()
    try:
        book = session.query(Book).filter(Book.title == book_title).one_or_none()
        if not book:
            book = Book(title=book_title)
            session.add(book)
            session.flush()

        chapter_by_title: dict[str, Chapter] = {
            chapter.title: chapter
            for chapter in session.query(Chapter).filter(Chapter.book_id == book.id).all()
        }
        verse_no_by_chapter: dict[int, int] = {}
        seen_hashes_by_chapter: dict[int, set[str]] = {}
        for chapter in chapter_by_title.values():
            max_verse = (
                session.query(Verse.verse_number)
                .filter(Verse.chapter_id == chapter.id)
                .order_by(Verse.verse_number.desc())
                .limit(1)
                .scalar()
            )
            verse_no_by_chapter[chapter.id] = int(max_verse or 0)
            existing_hashes = set()
            for row in session.query(Verse).filter(Verse.chapter_id == chapter.id).all():
                row_created_at = row.created_at or _utc_now()
                existing_payload = (
                    f"{_canonical_dt(row_created_at)}|{row.speaker}|{row.perspective}|"
                    f"{int(row.is_constitution_active)}|{row.content}"
                )
                existing_hashes.add(sha256(existing_payload.encode("utf-8")).hexdigest())
            seen_hashes_by_chapter[chapter.id] = existing_hashes

        entries: list[SourceEntry] = []
        for src_path, namespace in sources:
            entries.extend(_read_source(src_path, namespace=namespace))

        entries.sort(key=lambda e: (e.created_at, e.source, e.line_no))

        chapters_created = 0
        verses_created = 0
        verses_skipped_duplicate = 0

        for entry in entries:
            chapter_title = f"Session {entry.created_at.date().isoformat()}"
            chapter = chapter_by_title.get(chapter_title)
            if not chapter:
                chapter = Chapter(book_id=book.id, title=chapter_title, summary=None)
                session.add(chapter)
                session.flush()
                chapter_by_title[chapter_title] = chapter
                verse_no_by_chapter[chapter.id] = 0
                seen_hashes_by_chapter[chapter.id] = set()
                chapters_created += 1

            digest = _entry_hash(entry)
            if digest in seen_hashes_by_chapter[chapter.id]:
                verses_skipped_duplicate += 1
                continue

            verse_no_by_chapter[chapter.id] += 1
            verse = Verse(
                chapter_id=chapter.id,
                verse_number=verse_no_by_chapter[chapter.id],
                content=entry.content,
                speaker=entry.speaker,
                perspective=entry.perspective,
                is_constitution_active=entry.is_constitution_active,
                created_at=entry.created_at,
            )
            session.add(verse)
            seen_hashes_by_chapter[chapter.id].add(digest)
            verses_created += 1

        session.commit()
        return {
            "status": "ok",
            "db_path": db_path,
            "book_title": book_title,
            "sources": [str(src.resolve()) for src, _ in sources],
            "chapters_created": chapters_created,
            "verses_created": verses_created,
            "verses_skipped_duplicate": verses_skipped_duplicate,
        }
    finally:
        session.close()


def main() -> None:
    summary = migrate_memory()
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
