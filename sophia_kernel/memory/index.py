from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path


DEFAULT_MEMORY_ROOT = Path("/Users/dragonpd/Sophia/sophia_workspace/memory")
MEMORY_ROOT_ENV = "SOPHIA_MEMORY_ROOT"


def _memory_root() -> Path:
    return Path(os.getenv(MEMORY_ROOT_ENV, str(DEFAULT_MEMORY_ROOT)))


def _namespace_path(namespace: str) -> Path:
    if "/" in namespace or "\\" in namespace or namespace in {".", ".."}:
        raise ValueError("invalid namespace")
    return _memory_root() / f"{namespace}.jsonl"


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


def _read_records(namespace: str) -> list[dict]:
    path = _namespace_path(namespace)
    if not path.exists():
        return []

    records: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
    return records


def list_namespaces() -> list[str]:
    root = _memory_root()
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.jsonl") if p.is_file())


def count_records(namespace: str) -> int:
    return len(_read_records(namespace))


def recent_records(namespace: str, days: int = 7) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = _read_records(namespace)
    out: list[dict] = []
    for row in rows:
        ts = _parse_ts(str(row.get("ts", "")))
        if ts is None:
            continue
        if ts >= cutoff:
            out.append(row)
    return out


def tag_index(namespace: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in _read_records(namespace):
        data = row.get("data")
        if not isinstance(data, dict):
            continue
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and tag:
                counts[tag] += 1
    return dict(counts)


def decision_action_links() -> list[dict]:
    decisions = _read_records("decisions")
    actions = _read_records("actions")

    decision_titles: list[str] = []
    for row in decisions:
        data = row.get("data")
        if not isinstance(data, dict):
            continue
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            decision_titles.append(title.strip())

    links: list[dict] = []
    for action_row in actions:
        data = action_row.get("data")
        if not isinstance(data, dict):
            continue
        body = data.get("body")
        if not isinstance(body, str):
            continue
        body_lower = body.lower()
        action_title = data.get("title") if isinstance(data.get("title"), str) else ""

        for decision_title in decision_titles:
            if decision_title.lower() in body_lower:
                links.append(
                    {
                        "decision_title": decision_title,
                        "action_title": action_title,
                        "action_ts": action_row.get("ts", ""),
                    }
                )
    return links


def _summary_text() -> str:
    namespaces = list_namespaces()
    lines: list[str] = []
    lines.append("Memory Summary")
    lines.append("-------------")

    if not namespaces:
        lines.append("namespaces: none")
    else:
        for ns in namespaces:
            total = count_records(ns)
            tags = tag_index(ns)
            top_tags = sorted(tags.items(), key=lambda item: (-item[1], item[0]))[:5]
            if top_tags:
                tags_text = ", ".join(f"{k}({v})" for k, v in top_tags)
            else:
                tags_text = "(none)"
            lines.append(f"{ns}: total={total}, top_tags={tags_text}")

    links = decision_action_links()
    lines.append(f"decision→action linkage count: {len(links)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sophia memory index utilities")
    parser.add_argument("--summary", action="store_true", help="print index summary")
    args = parser.parse_args()

    if args.summary:
        print(_summary_text())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
