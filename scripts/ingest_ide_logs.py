from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor import executor


DROP_DIR = Path("/Users/dragonpd/Sophia/sophia_workspace/ingest_drop/ide_logs")
STATE_PATH = Path("/Users/dragonpd/Sophia/.sophia/ingest/ide_logs_state.json")
DROP_DIR_ENV = "SOPHIA_IDE_DROP_DIR"
STATE_PATH_ENV = "SOPHIA_IDE_STATE_PATH"
ALLOWED_EXTENSIONS = {".log", ".txt", ".md"}
MAX_FILES = 30
MAX_BYTES_PER_FILE = 200_000
MAX_CONTENT_CHARS = 4000
RAW_SNIPPET_CHARS = 200
MAX_RECENT_HASHES = 500
SECRET_MARKERS = [
    "OPENAI_API_KEY",
    "AWS_SECRET",
    "PASSWORD=",
    "TOKEN=",
]
_FILENAME_TS_RE = re.compile(r"^(?P<date>\d{8})(?:[_-]?(?P<time>\d{4,6}))?")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _drop_dir() -> Path:
    return Path(os.getenv(DROP_DIR_ENV, str(DROP_DIR)))


def _state_path() -> Path:
    return Path(os.getenv(STATE_PATH_ENV, str(STATE_PATH)))


def _default_state() -> dict:
    return {
        "recent_hashes": [],
        "last_scan_at": "",
        "ingested_total": 0,
    }


def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return _default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_state()
    if not isinstance(raw, dict):
        return _default_state()
    state = _default_state()
    state.update(raw)
    if not isinstance(state.get("recent_hashes"), list):
        state["recent_hashes"] = []
    if not isinstance(state.get("ingested_total"), int):
        state["ingested_total"] = 0
    return state


def _save_state(state: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _candidate_files(drop_dir: Path) -> list[Path]:
    if not drop_dir.exists():
        return []
    files = []
    for p in drop_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        rel = p.relative_to(drop_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:MAX_FILES]


def _infer_tool(path: Path) -> str:
    name = path.name.lower()
    if "codex" in name:
        return "codex"
    if "antigravity" in name or "anti_gravity" in name:
        return "anti-gravity"
    if "cursor" in name:
        return "cursor"
    return ""


def _read_limited_bytes(path: Path) -> tuple[bytes, bool]:
    with path.open("rb") as f:
        data = f.read(MAX_BYTES_PER_FILE + 1)
    truncated = len(data) > MAX_BYTES_PER_FILE
    if truncated:
        data = data[:MAX_BYTES_PER_FILE]
    return data, truncated


def _fingerprint(rel_path: str, data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contains_secret(text: str) -> bool:
    return any(marker in text for marker in SECRET_MARKERS)


def _identity(rel_path: str, mtime_ns: int, content_sha: str) -> str:
    return f"{rel_path}:{mtime_ns}:{content_sha}"


def _timestamp_from_filename(path: Path) -> str:
    m = _FILENAME_TS_RE.match(path.stem)
    if not m:
        return ""

    date_part = m.group("date")
    time_part = m.group("time") or "000000"
    if len(time_part) == 4:
        time_part = f"{time_part}00"
    elif len(time_part) > 6:
        time_part = time_part[:6]

    try:
        dt = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _extract_title_body(path: Path, text: str) -> tuple[str, str]:
    lines = text.splitlines()
    non_empty_idx = next((i for i, line in enumerate(lines) if line.strip()), None)

    if non_empty_idx is None:
        return path.name, ""

    if path.suffix.lower() == ".md":
        heading_idx = None
        heading = ""
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    heading_idx = i
                    heading = title
                    break
        if heading_idx is not None:
            body = "\n".join(lines[heading_idx + 1 :]).strip()
            return heading, body

    title = lines[non_empty_idx].strip()
    body = "\n".join(lines[non_empty_idx + 1 :]).strip()
    return title or path.name, body


def _normalize_record(path: Path, rel_path: str, text: str) -> dict:
    tags = ["ide", "log"]
    tool = _infer_tool(path)
    if tool:
        tags.append(tool)

    ts = _timestamp_from_filename(path)
    redacted = _contains_secret(text)
    if redacted:
        return {
            "kind": "ide_log",
            "source": "ide_drop",
            "file": path.name,
            "ts": ts,
            "title": path.name,
            "body": "[REDACTED_SECRET_CONTENT]",
            "tags": tags,
            "redacted": True,
            "skipped_reason": "secret_pattern",
        }

    try:
        clipped = text[:MAX_CONTENT_CHARS]
        title, body = _extract_title_body(path, clipped)
        record = {
            "kind": "ide_log",
            "source": "ide_drop",
            "file": path.name,
            "ts": ts,
            "title": title,
            "body": body.strip(),
            "tags": tags,
            "redacted": False,
        }
        if rel_path != path.name:
            record["source_path"] = rel_path
        return record
    except Exception:
        snippet = text[:RAW_SNIPPET_CHARS]
        record = {
            "kind": "ide_log",
            "source": "ide_drop",
            "file": path.name,
            "ts": ts,
            "title": path.name,
            "body": snippet,
            "tags": tags,
            "redacted": False,
            "parse_error": True,
        }
        if rel_path != path.name:
            record["source_path"] = rel_path
        return record


def ingest_ide_logs() -> dict:
    drop_dir = _drop_dir()
    drop_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state()

    recent_hashes = [str(x) for x in state.get("recent_hashes", [])]
    seen = set(recent_hashes)
    new_hashes: list[str] = []
    ingested = 0
    skipped = 0

    files = _candidate_files(drop_dir)
    for path in files:
        rel_path = str(path.relative_to(drop_dir))
        mtime_ns = path.stat().st_mtime_ns
        raw_bytes, file_truncated = _read_limited_bytes(path)
        content_sha = _fingerprint(rel_path, raw_bytes)
        identity = _identity(rel_path, mtime_ns, content_sha)

        if identity in seen:
            skipped += 1
            continue

        text = raw_bytes.decode("utf-8", errors="replace")
        record = _normalize_record(path, rel_path, text)
        record["ingested_at"] = _now_iso()
        record["content_truncated"] = file_truncated or len(text) > MAX_CONTENT_CHARS

        executor.execute_skill("memory.append", "0.1.0", {"namespace": "actions", "data": record})
        seen.add(identity)
        new_hashes.append(identity)
        ingested += 1

    merged = recent_hashes + new_hashes
    state["recent_hashes"] = merged[-MAX_RECENT_HASHES:]
    state["last_scan_at"] = _now_iso()
    state["ingested_total"] = int(state.get("ingested_total", 0)) + ingested
    _save_state(state)

    return {
        "scanned_files": len(files),
        "ingested": ingested,
        "skipped": skipped,
        "drop_dir": str(drop_dir),
        "state_path": str(_state_path()),
    }


def main() -> None:
    print(json.dumps(ingest_ide_logs(), ensure_ascii=False))


if __name__ == "__main__":
    main()
