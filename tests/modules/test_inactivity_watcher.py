from datetime import UTC, datetime, timedelta

from core.memory.schema import Book, Chapter, Verse, WorkPackage, create_session_factory
from sophia_kernel.modules.inactivity_watcher import run_inactivity_check


def _seed_old_activity(session):
    book = Book(title="Book of Beginnings")
    session.add(book)
    session.flush()
    chapter = Chapter(book_id=book.id, title="Session 2026-02-01")
    session.add(chapter)
    session.flush()

    old_at = datetime.now(UTC) - timedelta(days=8)
    verse = Verse(
        chapter_id=chapter.id,
        verse_number=1,
        content='{"__namespace":"notes","title":"old","body":"old"}',
        speaker="User",
        created_at=old_at,
    )
    session.add(verse)
    wp = WorkPackage(
        id="wp_old_001",
        title="Old work",
        description="incomplete",
        payload={},
        context_tag="work",
        status="READY",
        created_at=old_at,
        updated_at=old_at,
    )
    session.add(wp)
    session.commit()


def _append_observation_note(session_factory, payload: dict):
    session = session_factory()
    try:
        book = session.query(Book).filter(Book.title == "Book of Beginnings").one()
        chapter_title = f"Session {datetime.now(UTC).date().isoformat()}"
        chapter = session.query(Chapter).filter(Chapter.book_id == book.id, Chapter.title == chapter_title).one_or_none()
        if chapter is None:
            chapter = Chapter(book_id=book.id, title=chapter_title)
            session.add(chapter)
            session.flush()
            verse_number = 1
        else:
            current = (
                session.query(Verse)
                .filter(Verse.chapter_id == chapter.id)
                .order_by(Verse.verse_number.desc())
                .first()
            )
            verse_number = int(current.verse_number + 1) if current else 1
        verse = Verse(
            chapter_id=chapter.id,
            verse_number=verse_number,
            content='{"__namespace":"notes","note_type":"SOPHIA_ACTIVITY_OBSERVATION","system_generated":true}',
            speaker="Sophia",
            created_at=datetime.now(UTC),
        )
        session.add(verse)
        session.commit()
    finally:
        session.close()


def test_inactivity_watcher_triggers_once_with_conditions(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'watcher.db'}"
    session_factory = create_session_factory(db_url)
    session = session_factory()
    try:
        _seed_old_activity(session)
    finally:
        session.close()

    events: list[tuple[str, dict]] = []
    notes: list[dict] = []

    first = run_inactivity_check(
        session_factory=session_factory,
        write_event=lambda et, payload: events.append((et, payload)),
        append_note=lambda payload: (notes.append(payload), _append_observation_note(session_factory, payload)),
    )
    assert first["triggered"] is True
    assert events and events[0][0] == "USER_INACTIVITY_7D"
    assert notes and notes[0]["note_type"] == "SOPHIA_ACTIVITY_OBSERVATION"

    # cooldown should suppress immediate second trigger
    second = run_inactivity_check(
        session_factory=session_factory,
        write_event=lambda *_: None,
        append_note=lambda *_: None,
    )
    assert second["triggered"] is False
    assert second["reason"] in {"cooldown_active", "no_justified_condition", "threshold_not_met"}
