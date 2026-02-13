import json

from scripts import summarize_actions


def test_summarize_actions_appends_note_with_temp_memory_root(monkeypatch, tmp_path):
    memory_root = tmp_path / "memory"
    memory_root.mkdir(parents=True, exist_ok=True)
    actions_path = memory_root / "actions.jsonl"

    rows = [
        {
            "ts": "2026-02-13T00:00:00Z",
            "data": {
                "kind": "shell_command",
                "ts": "2026-02-13T00:00:00Z",
                "cmd": "git status",
                "cwd": "",
                "source": "zsh_history",
            },
        },
        {
            "ts": "2026-02-13T00:01:00Z",
            "data": {
                "kind": "shell_command",
                "ts": "2026-02-13T00:01:00Z",
                "cmd": "git commit -m test",
                "cwd": "",
                "source": "zsh_history",
            },
        },
        {
            "ts": "2026-02-13T00:02:00Z",
            "data": {
                "kind": "shell_command",
                "ts": "2026-02-13T00:02:00Z",
                "cmd": "[REDACTED_SECRET]",
                "cwd": "",
                "source": "zsh_history",
            },
        },
        {
            "ts": "2026-02-13T00:03:00Z",
            "data": {"kind": "other_event", "value": 1},
        },
    ]
    actions_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    calls: list[dict] = []
    monkeypatch.setenv("SOPHIA_MEMORY_ROOT", str(memory_root))
    monkeypatch.setattr(
        summarize_actions.executor,
        "execute_skill",
        lambda skill_id, version, inputs: calls.append(
            {"skill_id": skill_id, "version": version, "inputs": inputs}
        )
        or {"namespace": "notes", "records_appended": 1},
    )

    result = summarize_actions.summarize_actions()

    assert result == {"namespace": "notes", "records_appended": 1}
    assert len(calls) == 1
    assert calls[0]["skill_id"] == "memory.append"
    assert calls[0]["version"] == "0.1.0"
    assert calls[0]["inputs"]["namespace"] == "notes"

    note = calls[0]["inputs"]["data"]
    assert note["title"] == "작업 요약 (actions 최근 200)"
    assert note["tags"] == ["summary", "actions"]
    assert "git commit 여부: 있음" in note["body"]
    assert "위험 신호: [REDACTED_SECRET] 1건" in note["body"]
