from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.config import settings
from api.ledger_events import write_lifecycle_event
from core.forest.canopy import build_canopy_data
from core.forest.layout import ensure_project_layout, get_project_root, sanitize_project_name
from core.forest_logic import ProjectConstitution, StateManager, build_nodes_from_work_items
from core.services.forest_roadmap_sync_service import sync_roadmap_entries
from core.memory.schema import WorkPackage, create_session_factory

router = APIRouter(prefix="/sync", tags=["sync"])
session_factory = create_session_factory(settings.db_path)


class HandshakeInitRequest(BaseModel):
    project_name: str = Field(default="sophia", min_length=1, max_length=128)
    intent: str = Field(min_length=1, max_length=500)
    override_token: str | None = Field(default=None, max_length=256)


class SyncProgressItemRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    summary: str = Field(default="", max_length=1000)
    files: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=240)


class SyncProgressRequest(BaseModel):
    project_name: str = Field(default="sophia", min_length=1, max_length=128)
    mission_id: str | None = Field(default=None, max_length=128)
    progress_note: str | None = Field(default=None, max_length=300)
    items: list[SyncProgressItemRequest] = Field(default_factory=list)
    force_record: bool = False


class SyncCommitValidation(BaseModel):
    tests_passed: bool = False
    l2_passed: bool = False
    proof: list[str] = Field(default_factory=list)
    failure_reason: str | None = Field(default=None, max_length=300)


class SyncCommitRequest(BaseModel):
    project_name: str = Field(default="sophia", min_length=1, max_length=128)
    mission_id: str | None = Field(default=None, max_length=128)
    final_summary: str | None = Field(default=None, max_length=1000)
    items: list[SyncProgressItemRequest] = Field(default_factory=list)
    validation: SyncCommitValidation = Field(default_factory=SyncCommitValidation)
    force_record: bool = False


class SyncReconcileRequest(BaseModel):
    project_name: str = Field(default="sophia", min_length=1, max_length=128)
    apply: bool = True
    note: str | None = Field(default=None, max_length=240)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_constitution(project_name: str) -> ProjectConstitution:
    ensure_project_layout(project_name)
    path = get_project_root(project_name) / "status" / "constitution.json"
    raw = _load_json(path)
    anchor = str(raw.get("l1_anchor") or raw.get("L1_Anchor") or "").strip()
    if not anchor:
        anchor = f"{project_name} 프로젝트의 현재 목표를 명확하게 완료한다."

    rules_raw = raw.get("l2_rules")
    if not isinstance(rules_raw, list):
        rules_raw = raw.get("L2_Rules")
    rules = rules_raw if isinstance(rules_raw, list) else []

    index_raw = raw.get("l3_knowledge_index")
    if not isinstance(index_raw, list):
        index_raw = raw.get("L3_Knowledge_Index")
    index = index_raw if isinstance(index_raw, list) else []
    return ProjectConstitution(l1_anchor=anchor, l2_rules=rules, l3_knowledge_index=index)


def _load_work_items(project_name: str) -> list[dict[str, Any]]:
    session = session_factory()
    try:
        canopy = build_canopy_data(
            project_name=project_name,
            session=session,
            view="focus",
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
            limit=100,
            offset=0,
        )
    finally:
        session.close()

    roadmap = canopy.get("roadmap") if isinstance(canopy.get("roadmap"), dict) else {}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("in_progress", "pending", "done_recent"):
        items = roadmap.get(key) if isinstance(roadmap.get(key), list) else []
        for row in items:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id", "")).strip()
            if not row_id or row_id in seen:
                continue
            seen.add(row_id)
            rows.append(row)
    return rows


def _check_l2_violation(intent: str, rules: list[str]) -> str:
    lowered = str(intent or "").lower()
    for rule in rules:
        text = str(rule or "").strip()
        if not text:
            continue
        normalized = text.lower()
        if normalized.startswith("forbid:"):
            token = normalized.split(":", 1)[1].strip()
            if token and token in lowered:
                return f"L2 금지 규칙 위반: {token}"
    return ""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _project_name_for_work(row: WorkPackage) -> str:
    payload = row.payload if isinstance(row.payload, dict) else {}
    project = payload.get("project")
    if isinstance(project, str) and project.strip():
        return project.strip().lower()
    return "sophia"


def _read_journal_entries(path: Path, *, limit: int = 300) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    if len(rows) > limit:
        rows = rows[-limit:]
    return rows


def _latest_snapshot_entry(entries: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(entries):
        if "roadmap_now" in row and isinstance(row.get("roadmap_now"), dict):
            return row
    return {}


@router.post("/handshake/init")
async def sync_handshake_init(payload: HandshakeInitRequest):
    project_name = sanitize_project_name(payload.project_name)
    constitution = _load_constitution(project_name)
    work_items = _load_work_items(project_name)
    nodes = build_nodes_from_work_items(work_items)

    manager = StateManager(wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)))
    override = bool(str(payload.override_token or "").strip())
    l2_violation = _check_l2_violation(payload.intent, constitution.l2_rules)
    decision = manager.preflight(
        intent=payload.intent,
        constitution=constitution,
        nodes=nodes,
        override=override,
        l2_violation=l2_violation,
    )

    event_payload = {
        "project": project_name,
        "endpoint": "/sync/handshake/init",
        "task": "sync.handshake",
        "intent": payload.intent[:120],
        "allowed": bool(decision.allowed),
        "code": decision.code,
        "active_count": int(decision.snapshot.get("active_count", 0) or 0),
        "wip_limit": int(decision.snapshot.get("wip_limit", 1) or 1),
    }
    write_lifecycle_event(
        "SYNC_HANDSHAKE_INIT",
        event_payload,
        skill_id="forest.sync",
    )

    return {
        "status": "ok" if decision.allowed else "forbidden",
        "project": project_name,
        "handshake": decision.model_dump(mode="json"),
        "contract": {
            "name": "sync.handshake.v0.1",
            "requires_override_for_second_active": True,
        },
    }


@router.post("/progress")
async def sync_progress(payload: SyncProgressRequest):
    project_name = sanitize_project_name(payload.project_name)
    items = [
        {
            "title": str(item.title or "").strip(),
            "summary": str(item.summary or "").strip(),
            "files": [str(row).strip() for row in item.files if str(row).strip()],
            "tags": [str(row).strip() for row in item.tags if str(row).strip()],
            "category": str(item.category or "").strip(),
            "note": str(item.note or "").strip(),
        }
        for item in payload.items
    ]
    sync_result = sync_roadmap_entries(
        project_name=project_name,
        items=items,
        force_record=bool(payload.force_record),
        entry_type="SYNC_PROGRESS",
    )

    write_lifecycle_event(
        "SYNC_PROGRESS_REPORTED",
        {
            "project": project_name,
            "endpoint": "/sync/progress",
            "task": "sync.progress",
            "mission_id": str(payload.mission_id or "").strip(),
            "progress_note": str(payload.progress_note or "").strip()[:200],
            "received": int(sync_result["received"]),
            "recorded": int(sync_result["recorded"]),
            "skipped": int(sync_result["skipped"]),
            "path": str(sync_result["path"]),
        },
        skill_id="forest.sync",
    )

    return {
        "status": "ok",
        "project": project_name,
        "mission_id": str(payload.mission_id or "").strip(),
        "progress_note": str(payload.progress_note or "").strip(),
        **sync_result,
    }


@router.post("/commit")
async def sync_commit(payload: SyncCommitRequest):
    project_name = sanitize_project_name(payload.project_name)
    mission_id = str(payload.mission_id or "").strip()

    validation = payload.validation
    commit_status = "DONE" if (validation.tests_passed and validation.l2_passed) else "BLOCKED"

    updated_work: dict[str, Any] | None = None
    if mission_id:
        session = session_factory()
        try:
            row = session.query(WorkPackage).filter(WorkPackage.id == mission_id).first()
            if row is None:
                raise HTTPException(status_code=404, detail="mission_not_found")
            if _project_name_for_work(row) != project_name:
                raise HTTPException(status_code=403, detail="mission_project_mismatch")

            now = _utc_now()
            row.status = commit_status
            row.updated_at = now
            if commit_status == "DONE":
                row.completed_at = now
            else:
                row.completed_at = None
            payload_json = row.payload if isinstance(row.payload, dict) else {}
            payload_json["sync_commit"] = {
                "at": now.isoformat().replace("+00:00", "Z"),
                "tests_passed": bool(validation.tests_passed),
                "l2_passed": bool(validation.l2_passed),
                "proof": [str(item).strip() for item in validation.proof if str(item).strip()],
                "failure_reason": str(validation.failure_reason or "").strip(),
                "status": commit_status,
            }
            row.payload = payload_json
            session.commit()
            updated_work = {"id": row.id, "status": row.status}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    items = [
        {
            "title": str(item.title or "").strip(),
            "summary": str(item.summary or "").strip(),
            "files": [str(entry).strip() for entry in item.files if str(entry).strip()],
            "tags": [str(entry).strip() for entry in item.tags if str(entry).strip()],
            "category": str(item.category or "").strip(),
            "note": str(item.note or "").strip(),
        }
        for item in payload.items
    ]
    if not items:
        default_category = "FEATURE_ADD" if commit_status == "DONE" else "PROBLEM_FIX"
        summary = str(payload.final_summary or "").strip()
        if not summary:
            if commit_status == "DONE":
                summary = "commit validation passed"
            else:
                summary = str(validation.failure_reason or "").strip() or "commit validation failed"
        items = [
            {
                "title": f"mission {mission_id or 'unknown'} commit {commit_status}",
                "summary": summary,
                "files": [],
                "tags": ["sync", "commit"],
                "category": default_category,
                "note": "",
            }
        ]

    sync_result = sync_roadmap_entries(
        project_name=project_name,
        items=items,
        force_record=bool(payload.force_record),
        entry_type="SYNC_COMMIT",
    )

    write_lifecycle_event(
        "SYNC_COMMIT_APPLIED",
        {
            "project": project_name,
            "endpoint": "/sync/commit",
            "task": "sync.commit",
            "mission_id": mission_id,
            "commit_status": commit_status,
            "tests_passed": bool(validation.tests_passed),
            "l2_passed": bool(validation.l2_passed),
            "received": int(sync_result["received"]),
            "recorded": int(sync_result["recorded"]),
            "skipped": int(sync_result["skipped"]),
            "path": str(sync_result["path"]),
        },
        skill_id="forest.sync",
    )

    return {
        "status": "ok",
        "project": project_name,
        "mission_id": mission_id,
        "commit_status": commit_status,
        "work": updated_work,
        **sync_result,
    }


@router.post("/reconcile")
async def sync_reconcile(payload: SyncReconcileRequest):
    project_name = sanitize_project_name(payload.project_name)
    ensure_project_layout(project_name)
    status_dir = get_project_root(project_name) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    journal_path = status_dir / "roadmap_journal.jsonl"

    session = session_factory()
    try:
        canopy = build_canopy_data(
            project_name=project_name,
            session=session,
            view="focus",
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
            limit=100,
            offset=0,
        )
    finally:
        session.close()

    focus = canopy.get("focus") if isinstance(canopy.get("focus"), dict) else {}
    roadmap = canopy.get("roadmap") if isinstance(canopy.get("roadmap"), dict) else {}
    current_mission_id = str(focus.get("current_mission_id", "")).strip()
    current_remaining = int(roadmap.get("remaining_work", 0) or 0)
    current_next_action = str((focus.get("next_action") or {}).get("text", "")).strip()

    entries = _read_journal_entries(journal_path, limit=300)
    baseline = _latest_snapshot_entry(entries)
    mismatches: list[dict[str, Any]] = []

    if not baseline:
        mismatches.append({"code": "NO_BASELINE", "message": "로드맵 기준 스냅샷이 없습니다."})
    else:
        roadmap_now = baseline.get("roadmap_now") if isinstance(baseline.get("roadmap_now"), dict) else {}
        baseline_mission = str(roadmap_now.get("current_mission_id", "")).strip()
        baseline_remaining = int(roadmap_now.get("remaining_work", 0) or 0)

        if current_mission_id != baseline_mission:
            mismatches.append(
                {
                    "code": "MISSION_CHANGED",
                    "message": "현재 미션이 기준 스냅샷과 다릅니다.",
                    "baseline": baseline_mission,
                    "current": current_mission_id,
                }
            )
        if current_remaining != baseline_remaining:
            mismatches.append(
                {
                    "code": "REMAINING_WORK_CHANGED",
                    "message": "남은 작업 수가 기준 스냅샷과 다릅니다.",
                    "baseline": baseline_remaining,
                    "current": current_remaining,
                }
            )

    recorded = 0
    recorded_items: list[dict[str, Any]] = []
    skipped_items: list[dict[str, Any]] = []
    if payload.apply and mismatches:
        summary = "; ".join(str(row.get("message", "")).strip() for row in mismatches if str(row.get("message", "")).strip())
        sync_result = sync_roadmap_entries(
            project_name=project_name,
            items=[
                {
                    "title": "reconcile: focus drift detected",
                    "summary": summary or "reconcile mismatch detected",
                    "files": [],
                    "tags": ["sync", "reconcile"],
                    "category": "SYSTEM_CHANGE",
                    "note": str(payload.note or "").strip(),
                }
            ],
            force_record=False,
            entry_type="SYNC_RECONCILE",
        )
        recorded = int(sync_result["recorded"])
        recorded_items = sync_result["recorded_items"][:20]
        skipped_items = sync_result["skipped_items"][:20]

    write_lifecycle_event(
        "SYNC_RECONCILED",
        {
            "project": project_name,
            "endpoint": "/sync/reconcile",
            "task": "sync.reconcile",
            "mismatch_count": len(mismatches),
            "recorded": recorded,
            "current_mission_id": current_mission_id,
            "remaining_work": current_remaining,
        },
        skill_id="forest.sync",
    )

    return {
        "status": "ok",
        "project": project_name,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "current": {
            "mission_id": current_mission_id,
            "remaining_work": current_remaining,
            "next_action": current_next_action,
        },
        "baseline": {
            "exists": bool(baseline),
            "recorded_at": str(baseline.get("recorded_at", "")) if baseline else "",
            "mission_id": str(((baseline.get("roadmap_now") or {}).get("current_mission_id", "")) if baseline else ""),
            "remaining_work": int(((baseline.get("roadmap_now") or {}).get("remaining_work", 0)) if baseline else 0),
        },
        "applied": bool(payload.apply and mismatches),
        "recorded": recorded,
        "recorded_items": recorded_items,
        "skipped_items": skipped_items,
        "path": str(journal_path),
    }
