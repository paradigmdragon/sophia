import json

from scripts import migrate_memory
from core.memory.schema import Book, Chapter, Verse, create_session_factory


def _jsonl_write(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_migrate_memory_groups_by_date_and_creates_verses(tmp_path):
    notes_path = tmp_path / "notes.jsonl"
    actions_path = tmp_path / "actions.jsonl"
    db_path = tmp_path / "scripture.db"
    db_url = f"sqlite:///{db_path}"

    _jsonl_write(
        notes_path,
        [
            {
                "ts": "2026-02-14T10:00:00Z",
                "data": {"title": "N1", "body": "first note", "tags": ["notes"]},
            },
            {
                "ts": "2026-02-15T11:00:00Z",
                "data": {"title": "N2", "body": "second note", "tags": ["notes"]},
            },
        ],
    )
    _jsonl_write(
        actions_path,
        [
            {
                "ts": "2026-02-14T10:30:00Z",
                "data": {"kind": "chat_message", "role": "user", "text": "hello"},
            }
        ],
    )

    summary = migrate_memory.migrate_memory(
        db_path=db_url,
        notes_path=notes_path,
        chat_path=actions_path,
    )

    assert summary["status"] == "ok"
    assert summary["chapters_created"] == 2
    assert summary["verses_created"] == 3

    SessionLocal = create_session_factory(db_path=db_url)
    session = SessionLocal()
    try:
        books = session.query(Book).all()
        assert len(books) == 1
        assert books[0].title == "Book of Beginnings"

        chapters = session.query(Chapter).order_by(Chapter.title.asc()).all()
        assert [c.title for c in chapters] == ["Session 2026-02-14", "Session 2026-02-15"]

        verses = session.query(Verse).order_by(Verse.created_at.asc(), Verse.id.asc()).all()
        assert len(verses) == 3
        assert verses[0].verse_number == 1
        assert verses[1].verse_number == 2
        assert verses[2].verse_number == 1

        payload = json.loads(verses[0].content)
        assert payload["__namespace"] == "notes"
    finally:
        session.close()

