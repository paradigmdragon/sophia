import json
from datetime import UTC, datetime, timedelta

from sophia_kernel.memory import index


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_count_records(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    monkeypatch.setattr(index, "DEFAULT_MEMORY_ROOT", memory_root)

    _write_jsonl(
        memory_root / "notes.jsonl",
        [
            {"ts": "2026-02-13T00:00:00Z", "data": {"title": "n1"}},
            {"ts": "2026-02-13T00:01:00Z", "data": {"title": "n2"}},
            {"ts": "2026-02-13T00:02:00Z", "data": {"title": "n3"}},
        ],
    )

    assert index.count_records("notes") == 3


def test_recent_records_filter(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    monkeypatch.setattr(index, "DEFAULT_MEMORY_ROOT", memory_root)
    now = datetime.now(UTC)
    recent_ts = now.isoformat().replace("+00:00", "Z")
    old_ts = (now - timedelta(days=30)).isoformat().replace("+00:00", "Z")

    _write_jsonl(
        memory_root / "actions.jsonl",
        [
            {"ts": old_ts, "data": {"title": "old"}},
            {"ts": recent_ts, "data": {"title": "recent"}},
        ],
    )

    records = index.recent_records("actions", days=7)
    assert len(records) == 1
    assert records[0]["data"]["title"] == "recent"


def test_tag_aggregation(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    monkeypatch.setattr(index, "DEFAULT_MEMORY_ROOT", memory_root)

    _write_jsonl(
        memory_root / "notes.jsonl",
        [
            {"ts": "2026-02-13T00:00:00Z", "data": {"tags": ["a", "b"]}},
            {"ts": "2026-02-13T00:01:00Z", "data": {"tags": ["a"]}},
            {"ts": "2026-02-13T00:02:00Z", "data": {"tags": ["b", "c"]}},
        ],
    )

    tags = index.tag_index("notes")
    assert tags["a"] == 2
    assert tags["b"] == 2
    assert tags["c"] == 1


def test_decision_action_link_detection(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    monkeypatch.setattr(index, "DEFAULT_MEMORY_ROOT", memory_root)

    _write_jsonl(
        memory_root / "decisions.jsonl",
        [
            {
                "ts": "2026-02-13T00:00:00Z",
                "data": {"title": "Use append-only memory", "body": "decide"},
            }
        ],
    )
    _write_jsonl(
        memory_root / "actions.jsonl",
        [
            {
                "ts": "2026-02-13T00:01:00Z",
                "data": {
                    "title": "Implement writer",
                    "body": "Follow Use append-only memory in implementation",
                },
            },
            {
                "ts": "2026-02-13T00:02:00Z",
                "data": {"title": "Other action", "body": "No relation"},
            },
        ],
    )

    links = index.decision_action_links()
    assert len(links) == 1
    assert links[0]["decision_title"] == "Use append-only memory"
    assert links[0]["action_title"] == "Implement writer"
