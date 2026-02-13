import json

from scripts import ingest_ide_logs as ingest
from sophia_kernel.audit import ledger as audit_ledger
from sophia_kernel.registry import registry
from sophia_kernel.skills.memory import append as memory_append


def _register_memory_append() -> None:
    manifest = {
        "schema_version": "0.1",
        "version": "0.1.0",
        "skill_id": "memory.append",
        "scope": "manifest_memory",
        "entrypoint": "memory.append",
        "capabilities": ["memory.write"],
        "verification": {"mode": "advisory", "hook": "verify.default"},
        "rollback": {
            "strategy": "snapshot_restore",
            "backup_root": "/Users/dragonpd/Sophia/.sophia/backups",
        },
        "limits": {"timeout_ms": 30000, "max_retries": 0},
    }
    registry.register_skill(manifest)


def _setup_runtime(monkeypatch, tmp_path):
    drop_dir = tmp_path / "ide_logs"
    state_path = tmp_path / "ide_logs_state.json"
    registry_root = tmp_path / "registry" / "skills"
    memory_root = tmp_path / "memory"
    ledger_path = tmp_path / "audit" / "ledger.jsonl"

    drop_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("SOPHIA_IDE_DROP_DIR", str(drop_dir))
    monkeypatch.setenv("SOPHIA_IDE_STATE_PATH", str(state_path))
    monkeypatch.setattr(registry, "REGISTRY_ROOT", str(registry_root))
    monkeypatch.setattr(memory_append, "MEMORY_ROOT", memory_root)

    original_append = audit_ledger.append_audit_record

    def _append_to_tmp(record: dict) -> None:
        original_append(record, ledger_path=ledger_path)

    monkeypatch.setattr(ingest.executor.audit_ledger, "append_audit_record", _append_to_tmp)
    _register_memory_append()
    return drop_dir, state_path, memory_root, ledger_path


def _load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ingest_two_files_then_second_run_skips(monkeypatch, tmp_path):
    drop_dir, state_path, memory_root, ledger_path = _setup_runtime(monkeypatch, tmp_path)

    (drop_dir / "20260213_1015_codex.md").write_text(
        "# Work Summary\nImplemented registry v0.2\n",
        encoding="utf-8",
    )
    (drop_dir / "cursor_notes.txt").write_text(
        "Cursor sync\nAdjusted tests and scripts\n",
        encoding="utf-8",
    )

    first = ingest.ingest_ide_logs()
    second = ingest.ingest_ide_logs()

    assert first["scanned_files"] == 2
    assert first["ingested"] == 2
    assert first["skipped"] == 0
    assert first["drop_dir"] == str(drop_dir)
    assert first["state_path"] == str(state_path)
    assert second["scanned_files"] == 2
    assert second["ingested"] == 0
    assert second["skipped"] == 2
    actions_rows = _load_jsonl(memory_root / "actions.jsonl")
    assert len(actions_rows) == 2
    assert all(row["data"]["kind"] == "ide_log" for row in actions_rows)
    assert all(row["data"]["source"] == "ide_drop" for row in actions_rows)
    assert {row["data"]["file"] for row in actions_rows} == {"20260213_1015_codex.md", "cursor_notes.txt"}

    codex_row = next(row for row in actions_rows if row["data"]["file"] == "20260213_1015_codex.md")
    assert codex_row["data"]["title"] == "Work Summary"
    assert codex_row["data"]["ts"] == "2026-02-13T10:15:00Z"

    ledger_rows = _load_jsonl(ledger_path)
    assert len(ledger_rows) == 2
    assert all(row["status"] in {"committed", "failed"} for row in ledger_rows)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["ingested_total"] == 2
    assert len(state["recent_hashes"]) == 2


def test_secret_file_ingested_as_redacted(monkeypatch, tmp_path):
    drop_dir, _, memory_root, ledger_path = _setup_runtime(monkeypatch, tmp_path)
    (drop_dir / "secret_note.md").write_text(
        "# Secret\nTOKEN=abc123\n",
        encoding="utf-8",
    )

    result = ingest.ingest_ide_logs()
    assert result["ingested"] == 1

    actions_rows = _load_jsonl(memory_root / "actions.jsonl")
    assert len(actions_rows) == 1
    data = actions_rows[0]["data"]
    assert data["redacted"] is True
    assert data["body"] == "[REDACTED_SECRET_CONTENT]"
    assert data["skipped_reason"] == "secret_pattern"

    ledger_rows = _load_jsonl(ledger_path)
    assert len(ledger_rows) == 1
    assert ledger_rows[0]["status"] in {"committed", "failed"}
