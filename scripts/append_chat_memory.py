from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sophia_kernel.executor.executor import execute_skill


DEFAULT_CHANNEL = "General"
DEFAULT_NOTE_THRESHOLD = 240


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _append_actions_record(text: str, channel: str, ts: str) -> dict:
    payload = {
        "namespace": "actions",
        "data": {
            "kind": "chat_message",
            "ts": ts,
            "role": "user",
            "text": text,
            "channel": channel,
        },
    }
    return execute_skill("memory.append", "0.1.0", payload)


def _append_notes_record(text: str, channel: str, ts: str) -> dict:
    payload = {
        "namespace": "notes",
        "data": {
            "kind": "chat_message",
            "ts": ts,
            "role": "user",
            "text": text,
            "channel": channel,
        },
    }
    return execute_skill("memory.append", "0.1.0", payload)


def main() -> None:
    try:
        # Usage: python scripts/append_chat_memory.py <text> [channel] [threshold]
        if len(sys.argv) < 2:
            raise ValueError("Usage: append_chat_memory.py <text> [channel] [threshold]")

        text = sys.argv[1]
        channel = sys.argv[2] if len(sys.argv) >= 3 and sys.argv[2] else DEFAULT_CHANNEL
        threshold = (
            int(sys.argv[3])
            if len(sys.argv) >= 4 and sys.argv[3]
            else DEFAULT_NOTE_THRESHOLD
        )

        ts = _now_iso()
        actions_result = _append_actions_record(text=text, channel=channel, ts=ts)

        notes_result = None
        if len(text) > threshold:
            notes_result = _append_notes_record(text=text, channel=channel, ts=ts)

        print(
            json.dumps(
                {
                    "status": "ok",
                    "actions_appended": True,
                    "notes_appended": notes_result is not None,
                    "actions_result": actions_result,
                    "notes_result": notes_result,
                },
                ensure_ascii=False,
            )
        )
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
