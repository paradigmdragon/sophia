import json
from pathlib import Path

from scripts import ingest_shell_history as ingest


def test_ingest_shell_history_dedup_on_second_run(monkeypatch, tmp_path):
    history_path = tmp_path / "fake_zsh_history"
    history_path.write_text(
        "\n".join(
            [
                ": 1700000000:0;echo hello",
                ": 1700000001:0;echo world",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    state_path = tmp_path / "shell_history_state.json"
    calls: list[dict] = []

    monkeypatch.setattr(ingest, "HISTORY_PATH_CANDIDATES", [history_path])
    monkeypatch.setattr(ingest, "STATE_PATH", state_path)
    monkeypatch.setattr(
        ingest.executor,
        "execute_skill",
        lambda skill_id, version, inputs: calls.append(
            {"skill_id": skill_id, "version": version, "inputs": inputs}
        )
        or {"namespace": "actions", "records_appended": 1},
    )

    first = ingest.ingest_shell_history()
    second = ingest.ingest_shell_history()

    assert first["new_records"] == 2
    assert second["new_records"] == 0
    assert len(calls) == 2
    assert state_path.exists()

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["lines_processed"] == 2
    assert state["history_path"] == str(history_path)
    assert len(state["recent_hashes"]) == 2
