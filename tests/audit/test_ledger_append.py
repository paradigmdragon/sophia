import json

import pytest
from jsonschema.exceptions import ValidationError

from sophia_kernel.audit.ledger import append_audit_record


def _valid_record() -> dict:
    h = "sha256:" + ("a" * 64)
    return {
        "run_id": "run_1001",
        "skill_id": "workspace.read_only_check",
        "inputs_hash": h,
        "outputs_hash": h,
        "diff_refs": ["/Users/dragonpd/Sophia/.sophia/diffs/run_1001.patch"],
        "status": "committed",
        "timestamps": {
            "queued_at": "2026-02-12T10:00:00Z",
            "started_at": "2026-02-12T10:00:01Z",
            "finished_at": "2026-02-12T10:00:02Z",
        },
    }


def test_append_valid_record_creates_file_and_appends_line(tmp_path):
    ledger_path = tmp_path / "audit" / "ledger.jsonl"
    record = _valid_record()

    append_audit_record(record, ledger_path=ledger_path)

    assert ledger_path.exists()
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record


def test_append_invalid_record_raises_and_does_not_append(tmp_path):
    ledger_path = tmp_path / "audit" / "ledger.jsonl"
    record = _valid_record()
    del record["skill_id"]

    with pytest.raises(ValidationError):
        append_audit_record(record, ledger_path=ledger_path)

    assert not ledger_path.exists()
