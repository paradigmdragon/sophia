from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor import executor


HISTORY_PATH_CANDIDATES = [
    Path("~/.zsh_history").expanduser(),
    Path("~/.zhistory").expanduser(),
]
STATE_PATH = REPO_ROOT / ".sophia" / "ingest" / "shell_history_state.json"
MAX_HISTORY_LINES = 200
MAX_RECENT_HASHES = 500
SECRET_MARKERS = [
    "OPENAI_API_KEY",
    "AWS_SECRET",
    "PASSWORD=",
    "TOKEN=",
]
_ZSH_WITH_TS_PATTERN = re.compile(r"^: (\d+):\d+;(.*)$")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _default_state() -> dict:
    return {
        "last_run_at": "",
        "recent_hashes": [],
        "history_path": "",
        "lines_processed": 0,
    }


def _find_history_path() -> Path | None:
    for path in HISTORY_PATH_CANDIDATES:
        if path.exists():
            return path
    return None


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return _default_state()

    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_state()

    state = _default_state()
    state.update(raw if isinstance(raw, dict) else {})
    if not isinstance(state.get("recent_hashes"), list):
        state["recent_hashes"] = []
    return state


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _tail_lines(path: Path, n: int) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return list(deque((line.rstrip("\n") for line in f), maxlen=n))


def _parse_history_line(line: str) -> tuple[str, str]:
    m = _ZSH_WITH_TS_PATTERN.match(line)
    if m:
        epoch = m.group(1)
        cmd = m.group(2).strip()
        try:
            ts = (
                datetime.fromtimestamp(int(epoch), tz=UTC)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (ValueError, OSError, OverflowError):
            ts = ""
        return ts, cmd

    return "", line.strip()


def _has_secret(cmd: str) -> bool:
    return any(marker in cmd for marker in SECRET_MARKERS)


def _entry_hash(cmd: str, ts: str) -> str:
    payload = f"{cmd}{ts}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_entry(ts: str, cmd: str) -> dict:
    if _has_secret(cmd):
        return {"kind": "shell_command", "cmd": "[REDACTED_SECRET]", "source": "zsh_history"}

    return {
        "kind": "shell_command",
        "ts": ts,
        "cmd": cmd,
        "cwd": "",
        "source": "zsh_history",
    }


def ingest_shell_history() -> dict:
    history_path = _find_history_path()
    state = _load_state()

    if history_path is None:
        state["last_run_at"] = _utc_now_iso()
        state["history_path"] = ""
        state["lines_processed"] = 0
        _save_state(state)
        return {"history_path": "", "lines_processed": 0, "new_records": 0}

    lines = _tail_lines(history_path, MAX_HISTORY_LINES)

    recent_hashes = [str(h) for h in state.get("recent_hashes", [])]
    seen = set(recent_hashes)
    new_hashes: list[str] = []
    new_records = 0

    for line in lines:
        ts, cmd = _parse_history_line(line)
        if not cmd:
            continue

        h = _entry_hash(cmd, ts)
        if h in seen:
            continue

        entry = _normalize_entry(ts, cmd)
        executor.execute_skill("memory.append", "0.1.0", {"namespace": "actions", "data": entry})

        seen.add(h)
        new_hashes.append(h)
        new_records += 1

    merged = recent_hashes + new_hashes
    state["last_run_at"] = _utc_now_iso()
    state["recent_hashes"] = merged[-MAX_RECENT_HASHES:]
    state["history_path"] = str(history_path)
    state["lines_processed"] = len(lines)
    _save_state(state)

    return {
        "history_path": str(history_path),
        "lines_processed": len(lines),
        "new_records": new_records,
    }


def main() -> None:
    result = ingest_shell_history()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
