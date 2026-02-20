import json
from datetime import UTC, datetime

from core.engine.scheduler import SoneScheduler


def test_scheduler_executes_immediate_python_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "scheduler.db"
    db_url = f"sqlite:///{db_path}"
    scheduler = SoneScheduler(db_path=db_url, poll_interval_seconds=1)

    registered = scheduler.register_command(
        {
            "name": "python-sqrt",
            "type": "python",
            "priority": "P3",
            "payload": {"module": "math", "function": "sqrt", "args": [16], "kwargs": {}},
            "schedule": {"type": "immediate", "value": ""},
            "dependencies": [],
            "timeout": 30,
            "retry": {"count": 0, "delay": 0},
        }
    )
    assert registered["active"] is True

    summary = scheduler.run_due_once()
    assert summary["executed"] == 1
    assert scheduler.list_active_commands() == []

    day = datetime.now(UTC).date().isoformat()
    log_file = tmp_path / "logs" / "tasks" / f"{day}.jsonl"
    assert log_file.exists()
    rows = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    assert rows[0]["command_id"] == registered["command_id"]
    assert rows[0]["ok"] is True
