from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.forest.layout import ensure_project_layout, get_project_root
from core.services.forest_record_policy_service import (
    classify_record_entry,
    make_record_fingerprint,
    should_record_entry,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_existing_fingerprints(path: Path, *, limit: int = 500) -> set[str]:
    if not path.exists():
        return set()
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(line)
    fingerprints: set[str] = set()
    for line in rows[-limit:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        value = str(obj.get("fingerprint", "")).strip()
        if value:
            fingerprints.add(value)
    return fingerprints


def sync_roadmap_entries(
    *,
    project_name: str,
    items: list[dict[str, Any]],
    force_record: bool = False,
    entry_type: str = "SYNC_CHANGE",
) -> dict[str, Any]:
    ensure_project_layout(project_name)
    status_dir = get_project_root(project_name) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    journal_path = status_dir / "roadmap_journal.jsonl"

    existing_fingerprints = _read_existing_fingerprints(journal_path, limit=500)
    recorded_entries: list[dict[str, Any]] = []
    skipped_items: list[dict[str, Any]] = []

    for raw in items:
        row = raw if isinstance(raw, dict) else {}
        title = str(row.get("title", "")).strip()
        if not title:
            skipped_items.append({"title": "", "category": "CHORE", "reason": "invalid_title"})
            continue
        summary = str(row.get("summary", "")).strip()
        files = [str(item).strip() for item in (row.get("files") if isinstance(row.get("files"), list) else []) if str(item).strip()]
        tags = [str(item).strip() for item in (row.get("tags") if isinstance(row.get("tags"), list) else []) if str(item).strip()]
        category_hint = str(row.get("category", "")).strip()
        note = str(row.get("note", "")).strip()
        phase = str(row.get("phase", "")).strip()
        phase_step = str(row.get("phase_step", "")).strip()
        phase_title = str(row.get("phase_title", "")).strip()
        owner = str(row.get("owner", "")).strip()
        lane = str(row.get("lane", "")).strip()
        scope = str(row.get("scope", "")).strip()
        review_state = str(row.get("review_state", "")).strip()
        spec_refs = [
            str(item).strip()
            for item in (row.get("spec_refs") if isinstance(row.get("spec_refs"), list) else [])
            if str(item).strip()
        ]

        for tag in tags:
            low = tag.lower()
            if not owner and low.startswith("owner:"):
                owner = tag.split(":", 1)[1].strip()
            if not lane and low.startswith("lane:"):
                lane = tag.split(":", 1)[1].strip()
            if not scope and low.startswith("scope:"):
                scope = tag.split(":", 1)[1].strip()
            if not review_state and low.startswith("review_state:"):
                review_state = tag.split(":", 1)[1].strip()
            if low.startswith("spec_ref:"):
                ref = tag.split(":", 1)[1].strip()
                if ref:
                    spec_refs.append(ref)

        if not phase:
            for tag in tags:
                if tag.lower().startswith("phase:"):
                    phase = tag.split(":", 1)[1].strip()
                    break
        if not phase_step:
            for tag in tags:
                if tag.lower().startswith("phase_step:"):
                    phase_step = tag.split(":", 1)[1].strip()
                    break
        if phase and not phase_step:
            phase_step = f"{phase}.0"

        category, reason = classify_record_entry(
            title=title,
            summary=summary,
            files=files,
            tags=tags,
            category_hint=category_hint,
        )

        if not should_record_entry(category, force=force_record):
            skipped_items.append(
                {
                    "title": title,
                    "category": category,
                    "reason": f"policy_skip:{category}",
                }
            )
            continue

        fingerprint_summary = summary
        if note == "from_git":
            # from_git 항목은 intent 문구가 바뀌어도 동일 파일/제목이면 중복으로 간주한다.
            fingerprint_summary = ""

        fingerprint = make_record_fingerprint(
            project=project_name,
            category=category,
            title=title,
            summary=fingerprint_summary,
            files=files,
        )
        if fingerprint in existing_fingerprints:
            skipped_items.append(
                {
                    "title": title,
                    "category": category,
                    "reason": "duplicate",
                }
            )
            continue

        entry = {
            "recorded_at": _utc_now_iso(),
            "project": project_name,
            "type": str(entry_type or "SYNC_CHANGE").strip() or "SYNC_CHANGE",
            "category": category,
            "category_reason": reason,
            "title": title,
            "summary": summary,
            "files": files,
            "tags": tags,
            "note": note,
            "phase": phase,
            "phase_step": phase_step,
            "phase_title": phase_title,
            "owner": owner,
            "lane": lane,
            "scope": scope,
            "review_state": review_state,
            "spec_refs": sorted(set(spec_refs)),
            "fingerprint": fingerprint,
        }
        recorded_entries.append(entry)
        existing_fingerprints.add(fingerprint)

    if recorded_entries:
        with journal_path.open("a", encoding="utf-8") as file:
            for row in recorded_entries:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "path": str(journal_path),
        "received": len(items),
        "recorded": len(recorded_entries),
        "skipped": len(skipped_items),
        "recorded_items": recorded_entries,
        "skipped_items": skipped_items,
        "policy": {
            "tracked_categories": ["SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"],
            "force_record": bool(force_record),
            "ui_default": "skip",
        },
    }
