from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import memory_router
from core.memory.schema import create_session_factory


def _build_client(tmp_path) -> TestClient:
    db_path = tmp_path / "memory_api.db"
    db_url = f"sqlite:///{db_path}"
    memory_router._SessionLocal = create_session_factory(db_path=db_url)
    app = FastAPI()
    app.include_router(memory_router.router)
    return TestClient(app)


def test_memory_router_crud_flow(tmp_path):
    client = _build_client(tmp_path)

    create_res = client.post(
        "/memory/verse",
        json={
            "namespace": "notes",
            "date": "2026-02-14",
            "speaker": "User",
            "content": {
                "__namespace": "notes",
                "title": "Test note",
                "body": "Body text",
                "tags": ["test"],
            },
        },
    )
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["verse_number"] == 1
    assert created["namespace"] == "notes"

    books_res = client.get("/memory/books")
    assert books_res.status_code == 200
    books = books_res.json()
    assert len(books) == 1
    book_id = books[0]["id"]

    chapters_res = client.get(f"/memory/books/{book_id}")
    assert chapters_res.status_code == 200
    chapters = chapters_res.json()
    assert len(chapters) == 1
    chapter_id = chapters[0]["id"]
    assert chapters[0]["title"] == "Session 2026-02-14"

    verses_res = client.get(f"/memory/chapters/{chapter_id}")
    assert verses_res.status_code == 200
    verses = verses_res.json()
    assert len(verses) == 1
    assert verses[0]["parsed"]["title"] == "Test note"

    by_date_res = client.get("/memory/chapters", params={"date": "2026-02-14", "namespace": "notes"})
    assert by_date_res.status_code == 200
    by_date_items = by_date_res.json()["items"]
    assert len(by_date_items) == 1
    assert by_date_items[0]["parsed"]["body"] == "Body text"

    dates_res = client.get("/memory/dates", params={"namespace": "notes"})
    assert dates_res.status_code == 200
    assert dates_res.json()["dates"] == ["2026-02-14"]

