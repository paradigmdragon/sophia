import json

from scripts import daily_brief


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_run_daily_brief_appends_once_and_notes_only(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    state_path = tmp_path / "daily_brief_state.json"
    drop_dir = tmp_path / "drop"

    _write_jsonl(
        memory_root / "notes.jsonl",
        [
            {
                "ts": "2026-02-13T08:00:00Z",
                "data": {
                    "kind": "reflection_daily",
                    "date": "2026-02-13",
                    "next_actions": [
                        "테스트 정리/스모크 자동화",
                        "커밋 메시지 표준화/태깅",
                        "scripts 정돈/entrypoint 통일",
                    ],
                },
            }
        ],
    )

    calls: list[dict] = []
    monkeypatch.setenv("SOPHIA_MEMORY_ROOT", str(memory_root))
    monkeypatch.setenv("SOPHIA_DAILY_BRIEF_STATE_PATH", str(state_path))
    monkeypatch.setenv("SOPHIA_IDE_DROP_DIR", str(drop_dir))
    monkeypatch.setattr(
        daily_brief.executor,
        "execute_skill",
        lambda skill_id, version, inputs: calls.append(
            {"skill_id": skill_id, "version": version, "inputs": inputs}
        )
        or {"namespace": "notes", "records_appended": 1},
    )

    fixed_now = daily_brief.datetime(2026, 2, 13, 10, 0, tzinfo=daily_brief.UTC)
    first = daily_brief.run_daily_brief(now=fixed_now)
    second = daily_brief.run_daily_brief(now=fixed_now)

    assert first == {"date": "2026-02-13", "appended": True, "drop_file_created": True}
    assert second == {"date": "2026-02-13", "appended": False, "drop_file_created": False}
    assert len(calls) == 1

    call = calls[0]
    assert call["skill_id"] == "memory.append"
    assert call["version"] == "0.1.0"
    assert call["inputs"]["namespace"] == "notes"

    brief = call["inputs"]["data"]
    assert brief["kind"] == "ide_action_brief"
    assert brief["date"] == "2026-02-13"
    assert brief["title"] == "IDE 작업 지시서 (2026-02-13)"
    assert brief["source_ref"] == {"kind": "reflection_daily", "date": "2026-02-13"}
    assert len(brief["items"]) == 3
    assert brief["items"][0]["priority"] == 1
    assert brief["items"][0]["acceptance"] == "pytest 전체 green"
    assert "python -m pytest" in brief["items"][0]["commands"]

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_date"] == "2026-02-13"
