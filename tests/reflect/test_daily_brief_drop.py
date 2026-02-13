import json

from scripts import daily_brief


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_daily_brief_creates_drop_markdown_and_skips_second_run(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    state_path = tmp_path / "daily_brief_state.json"
    drop_dir = tmp_path / "ide_logs_drop"

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
                        "일반 작업 정리",
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

    fixed_now = daily_brief.datetime(2026, 2, 13, 10, 15, tzinfo=daily_brief.UTC)
    first = daily_brief.run_daily_brief(now=fixed_now)
    second = daily_brief.run_daily_brief(now=fixed_now)

    assert first == {"date": "2026-02-13", "appended": True, "drop_file_created": True}
    assert second == {"date": "2026-02-13", "appended": False, "drop_file_created": False}
    assert len(calls) == 1

    assert calls[0]["skill_id"] == "memory.append"
    assert calls[0]["version"] == "0.1.0"
    assert calls[0]["inputs"]["namespace"] == "notes"
    assert calls[0]["inputs"]["data"]["kind"] == "ide_action_brief"

    files = sorted(drop_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "# IDE 작업 지시서 (2026-02-13)" in content
    assert "## Source" in content
    assert content.count("### Priority") == 3

    files_after = sorted(drop_dir.glob("*.md"))
    assert len(files_after) == 1
