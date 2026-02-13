from __future__ import annotations

import json
import os
import sys
from collections import Counter, deque
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor import executor


DEFAULT_MEMORY_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace/memory")
MEMORY_ROOT_ENV = "SOPHIA_MEMORY_ROOT"
DEFAULT_LIMIT = 200


def _get_memory_root() -> Path:
    return Path(os.getenv(MEMORY_ROOT_ENV, str(DEFAULT_MEMORY_ROOT)))


def _tail_jsonl(path: Path, limit: int) -> list[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = deque((line.rstrip("\n") for line in f), maxlen=limit)

    rows: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _extract_shell_records(rows: list[dict]) -> list[dict]:
    records: list[dict] = []
    for row in rows:
        data = row.get("data")
        if not isinstance(data, dict):
            continue
        if data.get("kind") != "shell_command":
            continue
        records.append(data)
    return records


def _first_token(cmd: str) -> str:
    parts = cmd.strip().split()
    return parts[0] if parts else "(empty)"


def _make_body(records: list[dict]) -> str:
    cmds = [str(r.get("cmd", "")).strip() for r in records if str(r.get("cmd", "")).strip()]
    ts_values = [str(r.get("ts", "")).strip() for r in records if str(r.get("ts", "")).strip()]

    if ts_values:
        period = f"{ts_values[0]} ~ {ts_values[-1]}"
    else:
        period = "확인 필요"

    bucket_counter = Counter(_first_token(cmd) for cmd in cmds)
    bucket_parts = [f"{name}:{count}" for name, count in sorted(bucket_counter.items(), key=lambda x: (-x[1], x[0]))]
    bucket_text = ", ".join(bucket_parts) if bucket_parts else "없음"

    top_commands = Counter(cmds).most_common(3)
    if top_commands:
        top_lines = [f"{idx}. {cmd} ({count})" for idx, (cmd, count) in enumerate(top_commands, start=1)]
        top_text = "\n".join(top_lines)
    else:
        top_text = "1. 없음"

    has_git_commit = any(cmd.startswith("git commit") for cmd in cmds)
    redacted_count = sum(1 for cmd in cmds if cmd == "[REDACTED_SECRET]")

    return (
        f"기간: {period}\n"
        f"요약 통계: {bucket_text}\n"
        f"상위 명령 3개:\n{top_text}\n"
        f"git commit 여부: {'있음' if has_git_commit else '없음'}\n"
        f"위험 신호: [REDACTED_SECRET] {redacted_count}건"
    )


def summarize_actions(limit: int = DEFAULT_LIMIT) -> dict:
    memory_root = _get_memory_root()
    actions_path = memory_root / "actions.jsonl"
    rows = _tail_jsonl(actions_path, limit)
    records = _extract_shell_records(rows)

    note_data = {
        "title": "작업 요약 (actions 최근 200)",
        "body": _make_body(records),
        "tags": ["summary", "actions"],
        "refs": {"source": str(actions_path), "limit": limit},
        "v": "note_v0",
    }
    return executor.execute_skill(
        "memory.append",
        "0.1.0",
        {"namespace": "notes", "data": note_data},
    )


def main() -> None:
    result = summarize_actions()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
