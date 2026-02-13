from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor import executor


DEFAULT_MEMORY_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace/memory")
DEFAULT_STATE_DIR = Path("/Users/dragonpd/Sophia/.sophia/reflect")
DEFAULT_STATE_PATH = Path("/Users/dragonpd/Sophia/.sophia/reflect/daily_state.json")
MEMORY_ROOT_ENV = "SOPHIA_MEMORY_ROOT"
STATE_DIR_ENV = "SOPHIA_REFLECT_STATE_DIR"
STATE_PATH_ENV = "SOPHIA_REFLECT_STATE_PATH"

ACTION_LIMIT = 300
NOTES_LIMIT = 30
DECISIONS_LIMIT = 30

ERROR_KEYWORDS = [
    "PermissionError",
    "ModuleNotFoundError",
    "Traceback",
    "pytest",
    "failed",
    "No module named",
]
PROGRESS_KEYWORDS = [
    "git commit",
    "passed",
    "committed",
    "Implemented",
    "완료",
    "success",
]


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _today_str(now: datetime | None = None) -> str:
    current = now or _now_utc()
    return current.date().isoformat()


def _memory_root() -> Path:
    return Path(os.getenv(MEMORY_ROOT_ENV, str(DEFAULT_MEMORY_ROOT)))


def _state_dir() -> Path:
    return Path(os.getenv(STATE_DIR_ENV, str(DEFAULT_STATE_DIR)))


def _state_path() -> Path:
    override = os.getenv(STATE_PATH_ENV)
    if override:
        return Path(override)
    return _state_dir() / DEFAULT_STATE_PATH.name


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


def _parse_ts(value: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _first_token(cmd: str) -> str:
    parts = cmd.strip().split()
    return parts[0] if parts else "(empty)"


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"last_date": "", "last_note_hash": ""}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_date": "", "last_note_hash": ""}
    if not isinstance(raw, dict):
        return {"last_date": "", "last_note_hash": ""}
    return {
        "last_date": str(raw.get("last_date", raw.get("last_reflection_date", ""))),
        "last_note_hash": str(raw.get("last_note_hash", "")),
    }


def _save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _keyword_hits(texts: list[str], keywords: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in texts:
        lowered = text.lower()
        for kw in keywords:
            if kw.lower() in lowered:
                counts[kw] = counts.get(kw, 0) + 1
    return counts


def _collect_cmds(actions: list[dict]) -> list[str]:
    cmds: list[str] = []
    for row in actions:
        data = row.get("data")
        if isinstance(data, dict):
            cmd = data.get("cmd")
            if isinstance(cmd, str):
                stripped = cmd.strip()
                if stripped:
                    cmds.append(stripped)
    return cmds


def _collect_body_texts(notes: list[dict], decisions: list[dict]) -> list[str]:
    texts: list[str] = []
    for rows in (notes, decisions):
        for row in rows:
            data = row.get("data")
            if not isinstance(data, dict):
                continue
            for key in ("body",):
                val = data.get(key)
                if isinstance(val, str):
                    texts.append(val)
    return texts


def _next_actions(bucket_counts: Counter, redacted_count: int) -> list[str]:
    items: list[str] = []
    if bucket_counts.get("pytest", 0) > 0:
        items.append("테스트 정리/스모크 자동화")
    if bucket_counts.get("git", 0) > 0:
        items.append("커밋 메시지 표준화/태깅")
    if bucket_counts.get("python", 0) > 0:
        items.append("scripts 정돈/entrypoint 통일")
    if redacted_count > 0:
        items.append("비밀 패턴 확장/차단 강화")

    fallback = [
        "실패 패턴 재발 방지 체크리스트 작성",
        "진행 로그와 결정 로그 연결 점검",
        "내일 우선 작업 3개 확정",
    ]
    for item in fallback:
        if len(items) >= 3:
            break
        if item not in items:
            items.append(item)
    return items[:3]


def _hash_note(note: dict) -> str:
    payload = json.dumps(note, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_reflection_note(now: datetime | None = None) -> tuple[dict, dict]:
    current = now or _now_utc()
    date_str = _today_str(current)
    memory_root = _memory_root()

    actions_rows = _tail_jsonl(memory_root / "actions.jsonl", ACTION_LIMIT)
    notes_rows = _tail_jsonl(memory_root / "notes.jsonl", NOTES_LIMIT)
    decisions_rows = _tail_jsonl(memory_root / "decisions.jsonl", DECISIONS_LIMIT)

    actions_shell = [
        row.get("data")
        for row in actions_rows
        if isinstance(row.get("data"), dict) and row.get("data", {}).get("kind") == "shell_command"
    ]
    commands = _collect_cmds(actions_rows)
    bucket_counts = Counter(_first_token(cmd) for cmd in commands)
    top_commands = Counter(commands).most_common(3)
    redacted_count = sum(1 for cmd in commands if cmd == "[REDACTED_SECRET]")

    body_texts = _collect_body_texts(notes_rows, decisions_rows)
    combined_texts = commands + body_texts
    error_hits = _keyword_hits(combined_texts, ERROR_KEYWORDS)
    progress_hits = _keyword_hits(combined_texts, PROGRESS_KEYWORDS)

    missing: list[str] = []
    if not actions_rows:
        missing.append("actions 데이터 확인 필요")
    if not notes_rows:
        missing.append("notes 데이터 확인 필요")
    if not decisions_rows:
        missing.append("decisions 데이터 확인 필요")

    if not any(isinstance(data.get("ts"), str) and data.get("ts", "").strip() for data in actions_shell):
        missing.append("actions ts 확인 필요")

    note = {
        "kind": "reflection_daily",
        "date": date_str,
        "title": f"일일 리플렉션 ({date_str})",
        "summary": {
            "top_buckets": [
                {"token": token, "count": count}
                for token, count in sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
            ],
            "top_cmds": [{"cmd": cmd, "count": cnt} for cmd, cnt in top_commands],
            "new_records_scanned": len(actions_rows),
            "redacted_secret_count": redacted_count,
        },
        "signals": {
            "progress": [f"{kw}: {count}" for kw, count in sorted(progress_hits.items(), key=lambda item: (-item[1], item[0]))]
            or ["확인 필요"],
            "risk": [f"{kw}: {count}" for kw, count in sorted(error_hits.items(), key=lambda item: (-item[1], item[0]))]
            or ["확인 필요"],
            "missing": missing or ["확인 필요"],
        },
        "next_actions": _next_actions(bucket_counts, redacted_count),
    }
    meta = {"date": date_str, "hash": _hash_note(note)}
    return note, meta


def run_daily_reflection(now: datetime | None = None) -> dict:
    current = now or _now_utc()
    today = _today_str(current)
    state = _load_state()

    if state.get("last_date") == today:
        return {"date": today, "appended": False, "skipped": True}

    note, meta = build_reflection_note(current)
    executor.execute_skill(
        "memory.append",
        "0.1.0",
        {"namespace": "notes", "data": note},
    )

    state["last_date"] = meta["date"]
    state["last_note_hash"] = meta["hash"]
    _save_state(state)
    return {"date": today, "appended": True, "skipped": False}


def main() -> None:
    print(json.dumps(run_daily_reflection(), ensure_ascii=False))


if __name__ == "__main__":
    main()
