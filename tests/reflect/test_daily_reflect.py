import json

from scripts import daily_reflect


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_run_daily_reflection_appends_once_per_day(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    state_path = tmp_path / "daily_state.json"

    _write_jsonl(
        memory_root / "actions.jsonl",
        [
            {
                "ts": "2026-02-13T08:00:00Z",
                "data": {
                    "kind": "shell_command",
                    "ts": "2026-02-13T08:00:00Z",
                    "cmd": "pytest tests/executor",
                    "cwd": "",
                    "source": "zsh_history",
                },
            },
            {
                "ts": "2026-02-13T08:10:00Z",
                "data": {
                    "kind": "shell_command",
                    "ts": "2026-02-13T08:10:00Z",
                    "cmd": "git commit -m phase1",
                    "cwd": "",
                    "source": "zsh_history",
                },
            },
            {
                "ts": "2026-02-13T08:12:00Z",
                "data": {
                    "kind": "shell_command",
                    "ts": "2026-02-13T08:12:00Z",
                    "cmd": "[REDACTED_SECRET]",
                    "cwd": "",
                    "source": "zsh_history",
                },
            },
        ],
    )
    _write_jsonl(
        memory_root / "notes.jsonl",
        [
            {
                "ts": "2026-02-13T07:00:00Z",
                "data": {"title": "메모", "body": "Implemented module", "tags": ["summary"]},
            }
        ],
    )
    _write_jsonl(
        memory_root / "decisions.jsonl",
        [
            {
                "ts": "2026-02-13T06:00:00Z",
                "data": {"title": "Use strict gate", "body": "완료"},
            }
        ],
    )

    calls: list[dict] = []
    monkeypatch.setenv("SOPHIA_MEMORY_ROOT", str(memory_root))
    monkeypatch.setenv("SOPHIA_REFLECT_STATE_PATH", str(state_path))
    monkeypatch.setattr(
        daily_reflect.executor,
        "execute_skill",
        lambda skill_id, version, inputs: calls.append(
            {"skill_id": skill_id, "version": version, "inputs": inputs}
        )
        or {"namespace": "notes", "records_appended": 1},
    )

    fixed_now = daily_reflect.datetime(2026, 2, 13, 9, 0, tzinfo=daily_reflect.UTC)
    first = daily_reflect.run_daily_reflection(now=fixed_now)
    second = daily_reflect.run_daily_reflection(now=fixed_now)

    assert first == {"date": "2026-02-13", "appended": True, "skipped": False}
    assert second == {"date": "2026-02-13", "appended": False, "skipped": True}
    assert len(calls) == 1

    payload = calls[0]
    assert payload["skill_id"] == "memory.append"
    assert payload["version"] == "0.1.0"
    assert payload["inputs"]["namespace"] == "notes"

    note = payload["inputs"]["data"]
    assert note["kind"] == "reflection_daily"
    assert note["date"] == "2026-02-13"
    assert note["title"] == "일일 리플렉션 (2026-02-13)"
    assert note["summary"]["new_records_scanned"] == 3
    assert note["summary"]["redacted_secret_count"] == 1
    assert note["signals"]["missing"] == ["확인 필요"] or "확인 필요" in note["signals"]["missing"][0]
    assert isinstance(note["next_actions"], list)
    assert len(note["next_actions"]) == 3

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["last_date"] == "2026-02-13"
    assert state["last_note_hash"].startswith("sha256:")
