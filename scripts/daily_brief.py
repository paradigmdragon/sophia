from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor import executor


DEFAULT_MEMORY_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace/memory")
DEFAULT_STATE_DIR = Path("/Users/dragonpd/Sophia/.sophia/reflect")
DEFAULT_STATE_PATH = Path("/Users/dragonpd/Sophia/.sophia/reflect/daily_brief_state.json")
DROP_DIR = Path("/Users/dragonpd/Sophia/sophia_workspace/ingest_drop/ide_logs")
MEMORY_ROOT_ENV = "SOPHIA_MEMORY_ROOT"
STATE_DIR_ENV = "SOPHIA_REFLECT_STATE_DIR"
STATE_PATH_ENV = "SOPHIA_DAILY_BRIEF_STATE_PATH"
DROP_DIR_ENV = "SOPHIA_IDE_DROP_DIR"


def _today_str(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
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


def _drop_dir() -> Path:
    return Path(os.getenv(DROP_DIR_ENV, str(DROP_DIR)))


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"last_date": ""}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_date": ""}
    if not isinstance(raw, dict):
        return {"last_date": ""}
    return {"last_date": str(raw.get("last_date", ""))}


def _save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_notes_rows() -> list[dict]:
    notes_path = _memory_root() / "notes.jsonl"
    if not notes_path.exists():
        return []

    rows: list[dict] = []
    with notes_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _latest_reflection_for_date(date_str: str) -> dict | None:
    rows = _load_notes_rows()
    for row in reversed(rows):
        data = row.get("data")
        if not isinstance(data, dict):
            continue
        if data.get("kind") != "reflection_daily":
            continue
        if data.get("date") != date_str:
            continue
        return data
    return None


def _map_task(task: str) -> dict:
    lowered = task.lower()
    if "테스트" in task or "pytest" in lowered:
        return {
            "acceptance": "pytest 전체 green",
            "commands": ["source .venv/bin/activate", "python -m pytest"],
            "files": ["tests/"],
        }
    if "스모크" in task or "smoke" in lowered:
        return {
            "acceptance": "smoke 스크립트 0 exit",
            "commands": ["source .venv/bin/activate", "python scripts/<smoke>.py"],
            "files": ["scripts/"],
        }
    if "커밋" in task or "git" in lowered:
        return {
            "acceptance": "커밋 메시지 규칙 반영 + hooks 동작",
            "commands": ["git status", "git commit -m \"...\""],
            "files": [".git/hooks/", "scripts/"],
        }
    return {
        "acceptance": "notes에 결과 1건 기록",
        "commands": [],
        "files": [],
    }


def _build_items(next_actions: list[str]) -> list[dict]:
    tasks = [t for t in next_actions if isinstance(t, str) and t.strip()]
    while len(tasks) < 3:
        tasks.append("확인 필요")
    tasks = tasks[:3]

    items: list[dict] = []
    for idx, task in enumerate(tasks, start=1):
        mapped = _map_task(task)
        items.append(
            {
                "priority": idx,
                "task": task,
                "acceptance": mapped["acceptance"],
                "commands": mapped["commands"],
                "files": mapped["files"],
            }
        )
    return items


def _render_brief_markdown(brief: dict) -> str:
    lines = [
        f"# {brief['title']}",
        "",
        "## Source",
        f"reflection_daily ({brief['date']})",
        "",
        "## Tasks",
        "",
    ]

    for item in brief.get("items", []):
        lines.append(f"### Priority {item.get('priority', '')}")
        lines.append(f"Task: {item.get('task', '')}")
        lines.append("Acceptance:")
        lines.append(str(item.get("acceptance", "")))
        lines.append("")
        lines.append("Commands:")
        commands = item.get("commands", [])
        if isinstance(commands, list) and commands:
            lines.extend(f"- {cmd}" for cmd in commands)
        else:
            lines.append("- (none)")
        lines.append("")
        lines.append("Files:")
        files = item.get("files", [])
        if isinstance(files, list) and files:
            lines.extend(f"- {f}" for f in files)
        else:
            lines.append("- (none)")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _write_drop_file(brief: dict, now: datetime) -> Path:
    drop_dir = _drop_dir()
    drop_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%d_%H%M')}_sophia_brief.md"
    target = drop_dir / filename
    markdown = _render_brief_markdown(brief)
    with target.open("x", encoding="utf-8") as f:
        f.write(markdown)
    return target


def run_daily_brief(now: datetime | None = None) -> dict:
    current = now or datetime.now(UTC)
    today = _today_str(current)
    state = _load_state()
    if state.get("last_date") == today:
        return {"date": today, "appended": False, "drop_file_created": False}

    reflection = _latest_reflection_for_date(today)
    if reflection is None:
        return {
            "date": today,
            "appended": False,
            "drop_file_created": False,
        }

    next_actions = reflection.get("next_actions", [])
    if not isinstance(next_actions, list):
        next_actions = []

    brief = {
        "kind": "ide_action_brief",
        "date": today,
        "title": f"IDE 작업 지시서 ({today})",
        "source_ref": {"kind": "reflection_daily", "date": today},
        "items": _build_items(next_actions),
    }

    executor.execute_skill(
        "memory.append",
        "0.1.0",
        {"namespace": "notes", "data": brief},
    )
    _write_drop_file(brief, current)

    state["last_date"] = today
    _save_state(state)
    return {"date": today, "appended": True, "drop_file_created": True}


def main() -> None:
    print(json.dumps(run_daily_brief(), ensure_ascii=False))


if __name__ == "__main__":
    main()
