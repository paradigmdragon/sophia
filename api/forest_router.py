from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.config import settings
from api.ledger_events import write_lifecycle_event
from api.sophia_notes import append_system_note
from core.engine.local_brain import build_notice
from core.forest.canopy import build_canopy_data, export_canopy_dashboard, read_roadmap_journal
from core.forest.grove import analyze_to_forest
from core.forest.layout import (
    DEFAULT_PROJECT,
    append_project_ledger_event,
    ensure_project_layout,
    get_project_root,
    list_project_names,
    sanitize_project_name,
    write_json,
)
from core.memory.schema import ChatTimelineMessage, QuestionPool, WorkPackage, create_session_factory
from core.memory.schema import MindItem
from core.services.focus_policy_service import evaluate_focus_policy
from core.services.forest_record_policy_service import (
    classify_record_entry,
    make_record_fingerprint,
    should_record_entry,
)
from core.services.forest_roadmap_sync_service import sync_roadmap_entries
from core.services.forest_status_service import sync_progress_snapshot
from core.services.question_signal_service import upsert_question_signal
from sophia_kernel.modules.mind_diary import ingest_trigger_event, maybe_build_daily_diary

router = APIRouter(prefix="/forest", tags=["forest"])
session_factory = create_session_factory(settings.db_path)
BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BASE_DIR / "workspace"
SOPHIA_WORKSPACE_ROOT = BASE_DIR / "sophia_workspace"
SPEC_STATUS_VALUES = {"pending", "review", "confirmed", "unknown"}
SPEC_STATUS_ALIAS = {
    "draft": "pending",
    "pending": "pending",
    "review_requested": "review",
    "review": "review",
    "in_review": "review",
    "applied": "confirmed",
    "approved": "confirmed",
    "confirmed": "confirmed",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _normalize_context_tag(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw.startswith("forest:"):
        return raw
    if raw in {"question-queue", "work", "memo", "roots", "system"}:
        return raw
    return "work"


def _save_system_message(
    *,
    session,
    content: str,
    context_tag: str,
    linked_node: str | None = None,
) -> None:
    row = ChatTimelineMessage(
        id=f"msg_{uuid4().hex}",
        role="sophia",
        content=content,
        context_tag=context_tag,
        importance=0.65,
        emotion_signal=None,
        linked_cluster=None,
        linked_node=linked_node,
        status="normal",
        created_at=_utc_now(),
    )
    session.add(row)
    session.flush()


def _next_work_filename(work_dir: Path) -> str:
    current = sorted(work_dir.glob("package_*.md"))
    next_idx = len(current) + 1
    return f"package_{next_idx:03d}.md"


def _render_work_markdown(packet: dict[str, Any]) -> str:
    required = packet.get("acceptance_criteria", [])
    lines = [
        f"# Work Package {packet.get('id', '')}",
        f"Target: {packet.get('linked_node') or packet.get('context_tag') or ''}",
        f"Issue: {packet.get('title') or packet.get('issue') or ''}",
        "Required:",
    ]
    for item in required:
        lines.append(f"- {item}")
    deliverables = packet.get("deliverables", [])
    if deliverables:
        lines.append("")
        lines.append("Deliverables:")
        for item in deliverables:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def _extract_report_status(row: WorkPackage) -> str:
    payload = row.payload if isinstance(row.payload, dict) else {}
    report = payload.get("last_report")
    if isinstance(report, dict):
        status = str(report.get("status", "")).strip().upper()
        if status in {"DONE", "BLOCKED", "FAILED"}:
            return status
    status = str(row.status or "").strip().upper()
    if status in {"DONE", "BLOCKED", "FAILED"}:
        return status
    return ""


def _normalize_idea_tag(value: str) -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_", ":"}) else "-" for ch in raw)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-_") or "general"


def _idea_status(row: MindItem) -> str:
    tags = [str(tag).strip().lower() for tag in (row.tags or []) if str(tag).strip()]
    if "freeze_status:discarded" in tags or str(row.status) == "done":
        return "DISCARDED"
    if "freeze_status:promoted" in tags:
        return "PROMOTED"
    return "FROZEN"


def _serialize_idea(row: MindItem) -> dict[str, Any]:
    tags = [str(tag).strip().lower() for tag in (row.tags or []) if str(tag).strip()]
    idea_tag = "general"
    for tag in tags:
        if tag.startswith("idea_tag:"):
            idea_tag = tag.split(":", 1)[1].strip() or "general"
            break

    north_star = None
    proof_48h = None
    for bit in row.linked_bits or []:
        text = str(bit).strip()
        if text.startswith("north_star:"):
            north_star = text.split(":", 1)[1].strip() or None
        elif text.startswith("proof_48h:"):
            proof_48h = text.split(":", 1)[1].strip() or None

    return {
        "idea_id": str(row.id),
        "title": str(row.title or "").strip(),
        "tag": idea_tag,
        "status": _idea_status(row),
        "promote_requirements": {
            "north_star_link": north_star,
            "proof_48h": proof_48h,
        },
        "created_at": _to_iso(row.created_at),
        "updated_at": _to_iso(row.updated_at),
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _read_recent_fingerprints(path: Path, *, limit: int = 500) -> set[str]:
    if not path.exists():
        return set()
    rows: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(line)
    fingerprints: set[str] = set()
    for line in rows[-max(1, int(limit)):]:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        value = str(parsed.get("fingerprint", "")).strip()
        if value:
            fingerprints.add(value)
    return fingerprints


def _allowed_spec_roots(project_name: str) -> list[Path]:
    roots: list[Path] = []
    for candidate in [
        BASE_DIR / "Docs",
        BASE_DIR / "docs",
        BASE_DIR / "spec",
        get_project_root(project_name) / "docs",
    ]:
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if resolved.exists() and resolved.is_dir():
            roots.append(resolved)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _resolve_doc_path(project_name: str, raw_path: str) -> Path:
    text = str(raw_path or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="path is required")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (BASE_DIR / text).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"doc not found: {candidate}")
    if candidate.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise HTTPException(status_code=400, detail="doc must be .md/.markdown/.txt")
    allowed = _allowed_spec_roots(project_name)
    if not allowed:
        raise HTTPException(status_code=404, detail="no allowed doc roots")
    if not any(_is_within(candidate, root) for root in allowed):
        raise HTTPException(status_code=403, detail="doc path outside allowed roots")
    return candidate


def _read_doc_title(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as file:
            for _ in range(40):
                line = file.readline()
                if not line:
                    break
                text = line.strip()
                if text.startswith("# "):
                    return text[2:].strip()
                if text:
                    return text[:160]
    except OSError:
        return path.name
    return path.name


def _doc_type(path: Path) -> str:
    name = path.name.lower()
    if "constitution" in name or "헌법" in name:
        return "constitution"
    if "plan" in name or "roadmap" in name or "계획" in name:
        return "plan"
    if "spec" in name or "명세" in name:
        return "spec"
    if "guide" in name or "handoff" in name:
        return "guide"
    return "other"


def _normalize_spec_status(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    normalized = SPEC_STATUS_ALIAS.get(raw, raw)
    if normalized in SPEC_STATUS_VALUES:
        return normalized
    return "unknown"


def _sanitize_upload_filename(file_name: str, *, default_ext: str = ".md") -> str:
    text = str(file_name or "").strip()
    if not text:
        text = f"doc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}{default_ext}"
    text = text.replace("\\", "/").split("/")[-1]
    safe = "".join(ch if (ch.isalnum() or ch in {"-", "_", ".", " "}) else "_" for ch in text).strip(" ._")
    if not safe:
        safe = f"doc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}{default_ext}"
    suffix = Path(safe).suffix.lower()
    if suffix not in {".md", ".markdown", ".txt"}:
        safe = f"{safe}{default_ext}"
    return safe


def _next_available_doc_path(project_name: str, file_name: str) -> Path:
    docs_root = get_project_root(project_name) / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)
    target = docs_root / file_name
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    for idx in range(2, 10_000):
        candidate = docs_root / f"{stem}_v{idx}{suffix}"
        if not candidate.exists():
            return candidate
    return docs_root / f"{stem}_{uuid4().hex[:8]}{suffix}"


def _todo_file_path(project_name: str) -> Path:
    status_dir = get_project_root(project_name) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir / "todo_items.json"


def _load_todo_items(project_name: str) -> list[dict[str, Any]]:
    path = _todo_file_path(project_name)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in items:
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _save_todo_items(project_name: str, items: list[dict[str, Any]]) -> None:
    path = _todo_file_path(project_name)
    payload = {
        "project": project_name,
        "updated_at": _to_iso(_utc_now()),
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_todo_status(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"todo", "ready", "pending"}:
        return "todo"
    if raw in {"doing", "in_progress", "active"}:
        return "doing"
    if raw in {"done", "complete", "completed"}:
        return "done"
    return "todo"


def _sort_todo_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_rank = {"doing": 0, "todo": 1, "done": 2}
    return sorted(
        items,
        key=lambda row: (
            status_rank.get(_normalize_todo_status(str(row.get("status", ""))), 9),
            -int(row.get("priority_weight", 0) or 0),
            str(row.get("updated_at", "")),
            str(row.get("title", "")),
        ),
    )


def _status_from_category(category: str) -> str:
    normalized = str(category or "").strip().upper()
    if normalized == "SYSTEM_CHANGE":
        return "IN_PROGRESS"
    if normalized == "FEATURE_ADD":
        return "READY"
    if normalized == "PROBLEM_FIX":
        return "BLOCKED"
    return "DONE"


def _build_spec_index(*, project_name: str, limit: int = 200) -> list[dict[str, Any]]:
    roots = _allowed_spec_roots(project_name)
    doc_map: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
                continue
            doc_map[str(path.resolve())] = path.resolve()

    journal = read_roadmap_journal(project_name=project_name, limit=500)
    entries = journal.get("entries") if isinstance(journal.get("entries"), list) else []
    linked: dict[str, list[dict[str, Any]]] = {}
    reviewers: dict[str, set[str]] = {}

    for row in entries:
        if not isinstance(row, dict):
            continue
        files = [str(value).strip() for value in (row.get("files") if isinstance(row.get("files"), list) else []) if str(value).strip()]
        refs = [str(value).strip() for value in (row.get("spec_refs") if isinstance(row.get("spec_refs"), list) else []) if str(value).strip()]
        tags = [str(value).strip() for value in (row.get("tags") if isinstance(row.get("tags"), list) else []) if str(value).strip()]
        owner = str(row.get("owner", "")).strip().lower()
        for tag in tags:
            if not owner and tag.lower().startswith("owner:"):
                owner = tag.split(":", 1)[1].strip().lower()
        raw_candidates = [*files, *refs]
        for raw in raw_candidates:
            try:
                resolved = _resolve_doc_path(project_name, raw)
            except HTTPException:
                continue
            key = str(resolved)
            linked.setdefault(key, []).append(row)
            if owner:
                reviewers.setdefault(key, set()).add(owner)

    rows: list[dict[str, Any]] = []
    for key, path in doc_map.items():
        related = linked.get(key, [])
        ready = progress = done = blocked = 0
        latest_status = "unknown"
        latest_at = ""
        for entry in related:
            status = _status_from_category(str(entry.get("category", "")).strip())
            if status == "READY":
                ready += 1
            elif status == "IN_PROGRESS":
                progress += 1
            elif status == "BLOCKED":
                blocked += 1
            else:
                done += 1
            current_at = str(entry.get("recorded_at", "")).strip()
            if current_at and current_at > latest_at:
                latest_at = current_at
                latest_status = _normalize_spec_status(str(entry.get("review_state", "")).strip().lower())
        if latest_status not in {"pending", "review", "confirmed"}:
            if done > 0 and blocked == 0 and progress == 0:
                latest_status = "confirmed"
            elif blocked > 0:
                latest_status = "review"
            elif ready > 0 or progress > 0:
                latest_status = "pending"
            else:
                latest_status = "unknown"
        try:
            updated_at = _to_iso(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
        except OSError:
            updated_at = ""
        total = ready + progress + done + blocked
        rows.append(
            {
                "path": key,
                "title": _read_doc_title(path),
                "doc_type": _doc_type(path),
                "status": latest_status,
                "linked_records": int(len(related)),
                "reviewers": sorted(reviewers.get(key, set())),
                "progress": {
                    "ready": int(ready),
                    "in_progress": int(progress),
                    "done": int(done),
                    "blocked": int(blocked),
                    "total": int(total),
                },
                "updated_at": updated_at,
            }
        )

    rows.sort(
        key=lambda row: (
            -int(row.get("linked_records", 0) or 0),
            str(row.get("updated_at", "")),
            str(row.get("path", "")),
        ),
        reverse=True,
    )
    return rows[: max(1, int(limit or 1))]


def _load_project_snapshot_summary(project_name: str) -> dict[str, Any]:
    snapshot_path = get_project_root(project_name) / "status" / "progress_snapshot.json"
    if not snapshot_path.exists():
        return {
            "project_name": project_name,
            "progress_pct": 0,
            "remaining_work": 0,
            "blocked_count": 0,
            "unverified_count": 0,
            "updated_at": "",
            "current_phase": "",
            "current_phase_step": "",
            "roadmap_last_recorded_at": "",
        }
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    status_counts = summary.get("status_counts") if isinstance(summary.get("status_counts"), dict) else {}
    total_work = int(summary.get("work_total", 0) or 0)
    remaining_work = int(summary.get("remaining_work", 0) or 0)
    done_work = max(0, total_work - remaining_work)
    if total_work > 0:
        progress_pct = int(round((done_work / total_work) * 100.0))
    else:
        progress_pct = 0
    blocked_count = int(status_counts.get("BLOCKED", 0) or 0) + int(status_counts.get("FAILED", 0) or 0)
    unverified_count = int(status_counts.get("UNVERIFIED", 0) or 0)
    updated_at = str(payload.get("synced_at", "")).strip()
    if not updated_at:
        try:
            updated_at = _to_iso(datetime.fromtimestamp(snapshot_path.stat().st_mtime, tz=UTC))
        except OSError:
            updated_at = ""
    roadmap_journal = read_roadmap_journal(project_name=project_name, limit=20)
    current_phase = str(roadmap_journal.get("current_phase", "")).strip() if isinstance(roadmap_journal, dict) else ""
    current_phase_step = (
        str(roadmap_journal.get("current_phase_step", "")).strip() if isinstance(roadmap_journal, dict) else ""
    )
    roadmap_last_recorded_at = (
        str(roadmap_journal.get("last_recorded_at", "")).strip() if isinstance(roadmap_journal, dict) else ""
    )
    return {
        "project_name": project_name,
        "progress_pct": max(0, min(100, progress_pct)),
        "remaining_work": max(0, remaining_work),
        "blocked_count": max(0, blocked_count),
        "unverified_count": max(0, unverified_count),
        "updated_at": updated_at,
        "current_phase": current_phase,
        "current_phase_step": current_phase_step,
        "roadmap_last_recorded_at": roadmap_last_recorded_at,
    }


def _project_meta_path(project_name: str) -> Path:
    return get_project_root(project_name) / "status" / "project_meta.json"


def _read_project_meta(project_name: str) -> dict[str, Any]:
    path = _project_meta_path(project_name)
    if not path.exists():
        return {"archived": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["archived"] = bool(payload.get("archived", False))
    return payload


def _write_project_meta(project_name: str, payload: dict[str, Any]) -> None:
    path = _project_meta_path(project_name)
    write_json(path, payload)


def _record_live_roadmap_entry(
    *,
    project_name: str,
    title: str,
    summary: str,
    category: str = "SYSTEM_CHANGE",
    tags: list[str] | None = None,
    note: str = "",
    files: list[str] | None = None,
) -> dict[str, Any]:
    try:
        result = sync_roadmap_entries(
            project_name=project_name,
            items=[
                {
                    "title": str(title or "").strip(),
                    "summary": str(summary or "").strip(),
                    "files": [str(row).strip() for row in (files or []) if str(row).strip()],
                    "tags": [str(row).strip() for row in (tags or []) if str(row).strip()],
                    "category": str(category or "").strip(),
                    "note": str(note or "").strip(),
                }
            ],
            force_record=False,
            entry_type="LIVE_EVENT",
        )
        write_lifecycle_event(
            "FOREST_ROADMAP_LIVE_RECORDED",
            {
                "project": project_name,
                "title": str(title or "").strip()[:120],
                "category": str(category or "").strip(),
                "recorded": int(result.get("recorded", 0) or 0),
                "skipped": int(result.get("skipped", 0) or 0),
                "path": str(result.get("path", "")),
            },
            skill_id="forest.roadmap",
        )
        return result
    except Exception as exc:
        write_lifecycle_event(
            "FOREST_ROADMAP_LIVE_RECORD_FAILED",
            {
                "project": project_name,
                "title": str(title or "").strip()[:120],
                "category": str(category or "").strip(),
                "error": str(exc)[:240],
            },
            skill_id="forest.roadmap",
        )
        return {"recorded": 0, "skipped": 1, "recorded_items": [], "skipped_items": []}


def _seed_project_bootstrap_plan(*, project_name: str) -> dict[str, Any]:
    items = [
        {
            "title": "Phase 1.0 · 프로젝트 기준선 확정",
            "summary": "프로젝트 목적/범위/핵심 산출물 기준선을 고정합니다.",
            "category": "SYSTEM_CHANGE",
            "phase": "1",
            "phase_step": "1.0",
            "phase_title": "Bootstrap",
            "tags": ["phase:1", "phase_step:1.0", "bootstrap"],
            "files": ["docs/"],
            "note": "bootstrap_seed",
        },
        {
            "title": "Phase 1.1 · 소스자료 등록 및 Grove 분석",
            "summary": "명세/설계 자료를 등록하고 Grove 분석으로 질문/리스크를 생성합니다.",
            "category": "FEATURE_ADD",
            "phase": "1",
            "phase_step": "1.1",
            "phase_title": "Bootstrap",
            "tags": ["phase:1", "phase_step:1.1", "grove"],
            "files": ["forest/project/{project}/docs".replace("{project}", project_name)],
            "note": "bootstrap_seed",
        },
        {
            "title": "Phase 1.2 · 핵심 리스크/질문 정리",
            "summary": "고위험 질문을 확인하고 작업 패키지로 연결합니다.",
            "category": "PROBLEM_FIX",
            "phase": "1",
            "phase_step": "1.2",
            "phase_title": "Bootstrap",
            "tags": ["phase:1", "phase_step:1.2", "risk"],
            "files": ["forest/project/{project}/questions".replace("{project}", project_name)],
            "note": "bootstrap_seed",
        },
        {
            "title": "Phase 2.0 · 우선 구현 항목 착수",
            "summary": "핵심 기능 1개를 IN_PROGRESS로 전환하고 완료 기준을 확정합니다.",
            "category": "FEATURE_ADD",
            "phase": "2",
            "phase_step": "2.0",
            "phase_title": "Execution",
            "tags": ["phase:2", "phase_step:2.0", "execution"],
            "files": ["forest/project/{project}/work".replace("{project}", project_name)],
            "note": "bootstrap_seed",
        },
    ]
    return sync_roadmap_entries(
        project_name=project_name,
        items=items,
        force_record=False,
        entry_type="BOOTSTRAP",
    )


def _resolve_grove_source_path(*, project_name: str, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"source file not found: {candidate}")
    if candidate.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise HTTPException(status_code=400, detail="source file must be .md/.markdown/.txt")

    project_docs = get_project_root(project_name) / "docs"
    allowed_roots = [
        WORKSPACE_ROOT.resolve(),
        SOPHIA_WORKSPACE_ROOT.resolve(),
        (BASE_DIR / "Docs").resolve(),
        project_docs.resolve(),
    ]
    if not any(_is_within(candidate, root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="source path outside allowed roots")
    return candidate


class InitProjectRequest(BaseModel):
    project_name: str = Field(default="sophia", min_length=1, max_length=128)


class GroveAnalyzeRequest(BaseModel):
    doc_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    target: str = Field(default="auth-module")
    change: str = Field(default="변경 사항 확인 필요")
    scope: str | None = None
    linked_node: str | None = None


class GroveAnalyzePathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    target: str = Field(default="spec-module")
    change: str = Field(default="문서 변경 검토")
    scope: str | None = None
    linked_node: str | None = None


class GenerateWorkPackageRequest(BaseModel):
    kind: Literal["ANALYZE", "IMPLEMENT", "REVIEW", "MIGRATE"] = "ANALYZE"
    context_tag: str = "work"
    linked_node: str | None = None
    issue: str = Field(min_length=1)
    required: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    return_payload_spec: dict[str, Any] = Field(
        default_factory=lambda: {
            "work_package_id": "",
            "status": "DONE | BLOCKED | FAILED",
            "signals": [],
            "artifacts": [],
            "notes": "",
        }
    )
    title: str | None = None


class SeedInventoryWorkRequest(BaseModel):
    include_statuses: list[Literal["READY", "IN_PROGRESS", "BLOCKED"]] = Field(
        default_factory=lambda: ["READY", "IN_PROGRESS", "BLOCKED"]
    )
    limit: int = Field(default=8, ge=1, le=100)
    force: bool = False


class FreezeIdeaRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    tag: str = Field(min_length=1, max_length=48)


class PromoteIdeaRequest(BaseModel):
    north_star_link: str = Field(min_length=1, max_length=240)
    proof_48h: str = Field(min_length=1, max_length=240)
    promote_to_work: bool = True
    work_kind: Literal["ANALYZE", "IMPLEMENT", "REVIEW", "MIGRATE"] = "IMPLEMENT"
    work_context_tag: str = "work"


class RoadmapRecordRequest(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    summary: str | None = Field(default=None, max_length=1000)
    files: list[str] = Field(default_factory=list)
    spec_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=240)
    phase: str | None = Field(default=None, max_length=24)
    phase_step: str | None = Field(default=None, max_length=24)
    phase_title: str | None = Field(default=None, max_length=120)
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)
    scope: str | None = Field(default=None, max_length=24)
    review_state: str | None = Field(default=None, max_length=24)
    force_record: bool = False


class RoadmapSyncItemRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    summary: str = Field(default="", max_length=1000)
    files: list[str] = Field(default_factory=list)
    spec_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    category: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=240)
    phase: str | None = Field(default=None, max_length=24)
    phase_step: str | None = Field(default=None, max_length=24)
    phase_title: str | None = Field(default=None, max_length=120)
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)
    scope: str | None = Field(default=None, max_length=24)
    review_state: str | None = Field(default=None, max_length=24)


class RoadmapSyncRequest(BaseModel):
    items: list[RoadmapSyncItemRequest] = Field(default_factory=list)
    force_record: bool = False


class SpecReviewRequest(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    note: str | None = Field(default=None, max_length=400)
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)


class SpecUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    doc_type: Literal["constitution", "plan", "spec", "guide", "other"] = "spec"
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)
    note: str | None = Field(default=None, max_length=240)


class SpecStatusUpdateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    status: Literal["pending", "review", "confirmed"]
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)
    note: str | None = Field(default=None, max_length=400)


class SpecSonEReviewRequest(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    target: str = Field(default="spec-module", max_length=120)
    change: str = Field(default="명세 검토", max_length=160)
    scope: str | None = Field(default=None, max_length=120)
    owner: str | None = Field(default=None, max_length=48)
    lane: str | None = Field(default=None, max_length=48)
    note: str | None = Field(default=None, max_length=400)


class TodoUpsertRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=220)
    detail: str | None = Field(default=None, max_length=1000)
    priority_weight: int = Field(default=50, ge=1, le=100)
    category: str | None = Field(default=None, max_length=80)
    lane: str | None = Field(default=None, max_length=48)
    spec_ref: str | None = Field(default=None, max_length=400)
    status: Literal["todo", "doing", "done"] = "todo"


class TodoStatusRequest(BaseModel):
    status: Literal["todo", "doing", "done"] | None = None
    checked: bool | None = None


class ApplePlanSyncRequest(BaseModel):
    owner: str | None = Field(default="codex", max_length=48)
    lane: str | None = Field(default="codex", max_length=48)
    force: bool = False


def _apple_plan_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "apple_shortcuts_dod_a2",
            "title": "[APPLE] Shortcuts DoD-A2 실기기 검증",
            "priority_weight": 92,
            "detail": "실기기 Shortcuts 요청으로 trace_id 일치 증거 3종 확보 및 VERIFIED 승격",
            "category": "apple",
            "lane": "codex",
        },
        {
            "id": "apple_foundation_bridge_rehearsal",
            "title": "[APPLE] Foundation Bridge 헬스/타임아웃 리허설",
            "priority_weight": 88,
            "detail": "bridge up/down/timeout/host-blocked 시나리오 점검 후 fallback 품질 확인",
            "category": "apple",
            "lane": "codex",
        },
        {
            "id": "apple_generation_ethics_guard",
            "title": "[APPLE] generation_meta + ethics gate 회귀 점검",
            "priority_weight": 84,
            "detail": "provider/route/capabilities 누락/불일치 시 PENDING 처리와 reason code 검증",
            "category": "apple",
            "lane": "codex",
        },
        {
            "id": "apple_docs_status_sync",
            "title": "[APPLE] SSOT/체크리스트 문서 상태 동기화",
            "priority_weight": 78,
            "detail": "apple 문서 pending/review/confirmed 정리 및 다음 에이전트 인수인계 기준선 고정",
            "category": "apple",
            "lane": "codex",
        },
    ]


def _apple_plan_marker(plan_id: str) -> str:
    return f"[apple_plan_id:{plan_id}]"


def _build_apple_status_plan(project_name: str) -> dict[str, Any]:
    runtime = {
        "shortcuts_status": str(getattr(settings, "shortcuts_integration_status", "UNVERIFIED") or "UNVERIFIED").strip().upper(),
        "ai_provider_default": str(getattr(settings, "ai_provider_default", "ollama") or "ollama").strip(),
        "ai_mode": str(getattr(settings, "ai_mode", "fallback") or "fallback").strip(),
        "ai_foundation_bridge_url": str(getattr(settings, "ai_foundation_bridge_url", "http://127.0.0.1:8765") or "").strip(),
        "ai_allow_external": bool(getattr(settings, "ai_allow_external", False)),
    }
    docs_paths = [
        BASE_DIR / "Docs" / "apple" / "apple_intelligence_integration_ssot_v0_1.md",
        BASE_DIR / "Docs" / "apple" / "shortcuts_bridge_v0_1.md",
        BASE_DIR / "Docs" / "apple" / "manual_dod_a2_checklist.md",
    ]
    test_paths = [
        BASE_DIR / "tests" / "api" / "test_generation_meta_integration.py",
        BASE_DIR / "tests" / "api" / "test_ai_foundation_bridge_poc.py",
        BASE_DIR / "tests" / "ai" / "test_foundation_provider_phase2_poc.py",
    ]
    code_paths = [
        BASE_DIR / "api" / "chat_router.py",
        BASE_DIR / "core" / "llm" / "generation_meta.py",
        BASE_DIR / "core" / "ai" / "providers" / "foundation_provider.py",
    ]
    evidence = {
        "docs": [{"path": str(path), "exists": path.exists()} for path in docs_paths],
        "tests": [{"path": str(path), "exists": path.exists()} for path in test_paths],
        "code": [{"path": str(path), "exists": path.exists()} for path in code_paths],
    }
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "id": "shortcuts_integration",
            "title": "Shortcuts 요청 서명/메타 연동",
            "state": "done" if runtime["shortcuts_status"] == "VERIFIED" else "in_progress",
            "detail": f"SOPHIA_SHORTCUTS_STATUS={runtime['shortcuts_status']}",
        }
    )
    checks.append(
        {
            "id": "foundation_provider",
            "title": "Foundation Provider + Bridge 라우팅",
            "state": "done" if all(row["exists"] for row in evidence["code"]) else "blocked",
            "detail": "foundation_provider/generation_meta/chat_router 경로 점검",
        }
    )
    checks.append(
        {
            "id": "apple_test_suite",
            "title": "Apple/Bridge 회귀 테스트",
            "state": "done" if all(row["exists"] for row in evidence["tests"]) else "pending",
            "detail": "generation_meta + bridge POC 테스트 파일 존재 여부",
        }
    )
    checks.append(
        {
            "id": "apple_ssot_docs",
            "title": "Apple SSOT/운영 문서",
            "state": "done" if all(row["exists"] for row in evidence["docs"]) else "pending",
            "detail": "SSOT, 브리지 가이드, DoD-A2 체크리스트 문서 정합성",
        }
    )
    done_count = sum(1 for row in checks if str(row.get("state", "")).lower() == "done")
    progress_pct = int(round((done_count / len(checks)) * 100)) if checks else 0
    if runtime["shortcuts_status"] == "VERIFIED" and runtime["ai_provider_default"] in {"foundation", "apple"}:
        current_stage = "device_verified + foundation_primary"
    elif runtime["shortcuts_status"] == "VERIFIED":
        current_stage = "device_verified"
    elif runtime["ai_provider_default"] in {"foundation", "apple"}:
        current_stage = "foundation_poc"
    else:
        current_stage = "shortcuts_unverified"

    todo_items = _load_todo_items(project_name)
    plan_rows: list[dict[str, Any]] = []
    synced_count = 0
    for template in _apple_plan_templates():
        marker = _apple_plan_marker(str(template["id"]))
        existing = next(
            (
                row
                for row in todo_items
                if marker in str(row.get("detail", ""))
                or str(row.get("id", "")).strip() == f"todo_apple_{template['id']}"
            ),
            None,
        )
        status = _normalize_todo_status(str((existing or {}).get("status", "todo")))
        is_synced = existing is not None
        if is_synced:
            synced_count += 1
        plan_rows.append(
            {
                "id": str(template["id"]),
                "title": str((existing or {}).get("title", template["title"])),
                "priority_weight": int((existing or {}).get("priority_weight", template["priority_weight"]) or 0),
                "status": status,
                "detail": str((existing or {}).get("detail", f"{template['detail']} {marker}")).strip(),
                "category": str((existing or {}).get("category", template["category"])).strip(),
                "lane": str((existing or {}).get("lane", template["lane"])).strip() or "codex",
                "synced": is_synced,
            }
        )

    return {
        "status": "ok",
        "project": project_name,
        "runtime": runtime,
        "checks": checks,
        "progress_pct": progress_pct,
        "current_stage": current_stage,
        "plan": plan_rows,
        "todo_synced_count": synced_count,
        "todo_unsynced_count": max(0, len(plan_rows) - synced_count),
        "evidence": evidence,
    }


def _build_work_packet_from_idea(
    *,
    package_id: str,
    title: str,
    issue: str,
    kind: str,
    context_tag: str,
    linked_node: str | None,
    north_star_link: str,
    proof_48h: str,
) -> dict[str, Any]:
    acceptance = [
        f"north star 연결: {north_star_link.strip()}",
        f"48h 증명 계획: {proof_48h.strip()}",
        "완료 보고 JSON 제출",
    ]
    deliverables = ["return_payload.json"]
    return {
        "id": package_id,
        "kind": kind,
        "context_tag": context_tag,
        "linked_node": linked_node,
        "title": title,
        "issue": issue,
        "acceptance_criteria": acceptance,
        "deliverables": deliverables,
        "return_payload_spec": {
            "work_package_id": "",
            "status": "DONE | BLOCKED | FAILED",
            "signals": [],
            "artifacts": [],
            "notes": "",
        },
    }


def _build_work_packet_from_inventory(
    *,
    package_id: str,
    inventory_row: dict[str, Any],
) -> dict[str, Any]:
    feature = str(inventory_row.get("feature", "")).strip() or str(inventory_row.get("id", "")).strip()
    category = str(inventory_row.get("category", "")).strip()
    status = str(inventory_row.get("status", "")).strip().upper() or "IN_PROGRESS"
    risk_score = float(inventory_row.get("risk_score", 0.0) or 0.0)
    missing_files = [
        str(item).strip()
        for item in (inventory_row.get("missing_files") if isinstance(inventory_row.get("missing_files"), list) else [])
        if str(item).strip()
    ]
    required = [
        f"시스템 기능 정합성 확인: {feature}",
        f"현재 상태 {status} 해소",
    ]
    if risk_score >= 0.8:
        required.append(f"리스크 {risk_score:.2f} 원인 제거")
    if missing_files:
        required.append(f"누락 파일 {len(missing_files)}건 검토")
    required.append("완료 보고 JSON 제출")

    return {
        "id": package_id,
        "kind": "IMPLEMENT",
        "context_tag": "work",
        "linked_node": f"system:{str(inventory_row.get('id', '')).strip()}",
        "title": f"[SYS] {feature}",
        "issue": f"{category} · {feature} ({status})",
        "acceptance_criteria": required,
        "deliverables": ["return_payload.json"],
        "return_payload_spec": {
            "work_package_id": "",
            "status": "DONE | BLOCKED | FAILED",
            "signals": [],
            "artifacts": [],
            "notes": "",
        },
    }


def _seed_work_from_inventory_internal(
    *,
    session,
    project_name: str,
    include_statuses: set[str] | None = None,
    limit: int = 8,
    force: bool = False,
) -> dict[str, Any]:
    normalized_statuses = {str(item).strip().upper() for item in (include_statuses or set()) if str(item).strip()}
    normalized_statuses = {item for item in normalized_statuses if item in {"READY", "IN_PROGRESS", "BLOCKED"}}
    if not normalized_statuses:
        normalized_statuses = {"READY", "IN_PROGRESS", "BLOCKED"}
    safe_limit = max(1, min(int(limit or 8), 100))

    canopy_data = build_canopy_data(
        session=session,
        project_name=project_name,
        view="focus",
    )
    inventory_rows = canopy_data.get("system_inventory") if isinstance(canopy_data.get("system_inventory"), list) else []
    existing_rows = session.query(WorkPackage).order_by(WorkPackage.created_at.asc(), WorkPackage.id.asc()).all()
    existing_ids: set[str] = set()
    for row in existing_rows:
        row_payload = row.payload if isinstance(row.payload, dict) else {}
        if str(row_payload.get("project", "")).strip() != project_name:
            continue
        if str(row_payload.get("source", "")).strip() != "system_inventory":
            continue
        inventory_id = str(row_payload.get("inventory_id", "")).strip()
        if inventory_id:
            existing_ids.add(inventory_id)

    candidates: list[dict[str, Any]] = []
    for raw in inventory_rows:
        if not isinstance(raw, dict):
            continue
        inventory_id = str(raw.get("id", "")).strip()
        if not inventory_id:
            continue
        status = str(raw.get("status", "")).strip().upper()
        if status not in normalized_statuses:
            continue
        candidates.append(raw)

    candidates.sort(
        key=lambda row: (
            -1 if str(row.get("status", "")).upper() in {"BLOCKED", "FAILED"} else 0,
            -float(row.get("risk_score", 0.0) or 0.0),
            int(row.get("progress_pct", 0) or 0),
            str(row.get("feature", "")),
        )
    )

    work_dir = get_project_root(project_name) / "work"
    created: list[dict[str, Any]] = []
    skipped_existing = 0
    skipped_limit = 0
    for raw in candidates:
        inventory_id = str(raw.get("id", "")).strip()
        if not force and inventory_id in existing_ids:
            skipped_existing += 1
            continue
        if len(created) >= safe_limit:
            skipped_limit += 1
            continue

        package_id = f"wp_{uuid4().hex}"
        packet = _build_work_packet_from_inventory(package_id=package_id, inventory_row=raw)
        title = str(packet.get("title", "")).strip() or package_id
        description = str(packet.get("issue", "")).strip() or title
        linked_node = str(packet.get("linked_node", "")).strip() or None
        context_tag = _normalize_context_tag(str(packet.get("context_tag", "work")))

        work_row = WorkPackage(
            id=package_id,
            title=title,
            description=description,
            payload={
                "work_packet": packet,
                "project": project_name,
                "source": "system_inventory",
                "inventory_id": inventory_id,
                "inventory_status": str(raw.get("status", "")).strip().upper(),
            },
            context_tag=context_tag,
            status="READY",
            linked_node=linked_node,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(work_row)

        filename = _next_work_filename(work_dir)
        md_path = work_dir / filename
        md_path.write_text(_render_work_markdown(packet), encoding="utf-8")

        created.append(
            {
                "work_package_id": package_id,
                "inventory_id": inventory_id,
                "title": title,
                "md_path": str(md_path),
            }
        )
        existing_ids.add(inventory_id)

    if created:
        _save_system_message(
            session=session,
            content=f"시스템 인벤토리 기반 작업 {len(created)}건 생성 완료",
            context_tag="work",
            linked_node="forest:system_inventory",
        )

    return {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_limit": skipped_limit,
        "include_statuses": sorted(normalized_statuses),
        "limit": safe_limit,
    }


def _enforce_focus_lock_for_work_mutation(*, session, project_name: str, operation: str) -> None:
    policy = evaluate_focus_policy(
        session=session,
        project_name=project_name,
        focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
        focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
        wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        operation=operation,
    )
    if not bool(policy.get("blocked", False)):
        return
    next_action = policy.get("next_action") if isinstance(policy.get("next_action"), dict) else {}
    next_text = str(next_action.get("text", "")).strip() or "현재 미션 완료 후 다시 시도"
    reason = str(policy.get("reason", "")).strip() or "FOCUS_LOCK_ACTIVE"
    raise HTTPException(
        status_code=409,
        detail={
            "code": "FOCUS_LOCKED",
            "operation": operation,
            "project": project_name,
            "reason": reason,
            "current_mission_id": str(policy.get("current_mission_id", "") or ""),
            "next_action": next_text,
            "wip_active_count": int(policy.get("wip_active_count", 0) or 0),
            "wip_limit": int(policy.get("wip_limit", 1) or 1),
            "focus_lock_level": str(policy.get("focus_lock_level", "soft")),
        },
    )


@router.post("/projects/init")
async def init_project(payload: InitProjectRequest):
    project_name = sanitize_project_name(payload.project_name)
    paths = ensure_project_layout(project_name)
    bootstrap = {"recorded": 0, "skipped": 0, "path": "", "error": ""}
    inventory_seed = {
        "status": "skipped",
        "created_count": 0,
        "skipped_existing": 0,
        "skipped_limit": 0,
        "limit": 0,
        "include_statuses": [],
        "error": "",
    }
    try:
        bootstrap_raw = _seed_project_bootstrap_plan(project_name=project_name)
        bootstrap = {
            "recorded": int(bootstrap_raw.get("recorded", 0) or 0),
            "skipped": int(bootstrap_raw.get("skipped", 0) or 0),
            "path": str(bootstrap_raw.get("path", "")),
            "error": "",
        }
        if bootstrap["recorded"] > 0:
            append_project_ledger_event(
                project_name=project_name,
                event_type="ROADMAP_BOOTSTRAP",
                target=project_name,
                summary=f"bootstrap roadmap seeded ({bootstrap['recorded']})",
                payload={"recorded": bootstrap["recorded"], "skipped": bootstrap["skipped"]},
            )
    except Exception as exc:
        bootstrap["error"] = str(exc)[:240]
        write_lifecycle_event(
            "FOREST_BOOTSTRAP_SEED_FAILED",
            {"project": project_name, "error": bootstrap["error"]},
            skill_id="forest.bootstrap",
        )

    seed_session = session_factory()
    try:
        seeded = _seed_work_from_inventory_internal(
            session=seed_session,
            project_name=project_name,
            include_statuses={"READY", "IN_PROGRESS", "BLOCKED"},
            limit=8,
            force=False,
        )
        seed_session.commit()
        inventory_seed = {
            "status": "ok",
            "created_count": len(seeded.get("created", [])),
            "skipped_existing": int(seeded.get("skipped_existing", 0) or 0),
            "skipped_limit": int(seeded.get("skipped_limit", 0) or 0),
            "limit": int(seeded.get("limit", 0) or 0),
            "include_statuses": seeded.get("include_statuses", []),
            "error": "",
        }
    except Exception as exc:
        seed_session.rollback()
        inventory_seed = {
            "status": "error",
            "created_count": 0,
            "skipped_existing": 0,
            "skipped_limit": 0,
            "limit": 0,
            "include_statuses": [],
            "error": str(exc)[:240],
        }
        write_lifecycle_event(
            "FOREST_INIT_WORK_SEED_FAILED",
            {"project": project_name, "error": inventory_seed["error"]},
            skill_id="forest.work",
        )
    finally:
        seed_session.close()

    if int(inventory_seed.get("created_count", 0) or 0) > 0:
        append_project_ledger_event(
            project_name=project_name,
            event_type="WORK_PACKAGE_CREATED",
            target=f"inventory:{project_name}",
            summary=f"init inventory seed created={inventory_seed['created_count']}",
            payload={
                "created_count": int(inventory_seed.get("created_count", 0) or 0),
                "skipped_existing": int(inventory_seed.get("skipped_existing", 0) or 0),
                "skipped_limit": int(inventory_seed.get("skipped_limit", 0) or 0),
            },
        )

    sync_result = {"status": "skipped", "snapshot_path": "", "roadmap_path": "", "remaining_work": 0}
    session = session_factory()
    try:
        canopy_data = build_canopy_data(session=session, project_name=project_name)
        synced = sync_progress_snapshot(project_name=project_name, canopy_data=canopy_data)
        summary = synced.get("snapshot", {}).get("summary", {}) if isinstance(synced.get("snapshot"), dict) else {}
        sync_result = {
            "status": "ok",
            "snapshot_path": str(synced.get("snapshot_path", "")),
            "roadmap_path": str(synced.get("roadmap_path", "")),
            "remaining_work": int(summary.get("remaining_work", 0) or 0),
        }
    except Exception as exc:
        sync_result = {
            "status": "error",
            "snapshot_path": "",
            "roadmap_path": "",
            "remaining_work": 0,
            "error": str(exc)[:240],
        }
        write_lifecycle_event(
            "FOREST_INIT_STATUS_SYNC_FAILED",
            {"project": project_name, "error": sync_result["error"]},
            skill_id="forest.status",
        )
    finally:
        session.close()

    append_project_ledger_event(
        project_name=project_name,
        event_type="PROJECT_INIT",
        target=project_name,
        summary="Forest project layout initialized",
        payload={"bootstrap_recorded": bootstrap.get("recorded", 0), "sync_status": sync_result.get("status", "skipped")},
    )
    return {
        "status": "ok",
        "project": project_name,
        "paths": paths,
        "bootstrap": bootstrap,
        "inventory_seed": inventory_seed,
        "status_sync": sync_result,
    }


@router.get("/projects")
async def list_projects(include_archived: bool = Query(default=False)):
    ensure_project_layout(DEFAULT_PROJECT)
    rows: list[dict[str, Any]] = []
    for name in list_project_names():
        meta = _read_project_meta(name)
        archived = bool(meta.get("archived", False))
        if archived and not include_archived:
            continue
        row = _load_project_snapshot_summary(name)
        row["archived"] = archived
        row["archived_at"] = str(meta.get("archived_at", "")).strip()
        rows.append(row)
    rows.sort(
        key=lambda row: (
            0 if str(row.get("project_name", "")) == DEFAULT_PROJECT else 1,
            1 if bool(row.get("archived", False)) else 0,
            str(row.get("project_name", "")),
        )
    )
    return {"status": "ok", "projects": rows}


@router.post("/projects/{project_name}/archive")
async def archive_project(project_name: str):
    safe_project = sanitize_project_name(project_name)
    if safe_project == DEFAULT_PROJECT:
        raise HTTPException(status_code=400, detail="default project cannot be archived")
    ensure_project_layout(safe_project)
    meta = _read_project_meta(safe_project)
    meta["archived"] = True
    meta["archived_at"] = _to_iso(_utc_now())
    _write_project_meta(safe_project, meta)
    append_project_ledger_event(
        project_name=safe_project,
        event_type="PROJECT_ARCHIVED",
        target=safe_project,
        summary="project archived",
    )
    return {"status": "ok", "project": safe_project, "archived": True}


@router.post("/projects/{project_name}/unarchive")
async def unarchive_project(project_name: str):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    meta = _read_project_meta(safe_project)
    meta["archived"] = False
    meta["archived_at"] = ""
    _write_project_meta(safe_project, meta)
    append_project_ledger_event(
        project_name=safe_project,
        event_type="PROJECT_UNARCHIVED",
        target=safe_project,
        summary="project unarchived",
    )
    return {"status": "ok", "project": safe_project, "archived": False}


@router.post("/projects/{project_name}/grove/analyze")
async def grove_analyze(project_name: str, payload: GroveAnalyzeRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)

    analysis = analyze_to_forest(
        project_name=safe_project,
        doc_name=payload.doc_name,
        content=payload.content,
        target=payload.target.strip(),
        change=payload.change.strip(),
        scope=payload.scope,
        write_doc=True,
    )

    session = session_factory()
    try:
        pending_messages = []
        for signal in analysis.get("signals", []):
            _, pending = upsert_question_signal(
                session=session,
                cluster_id=str(signal["cluster_id"]),
                description=str(signal["description"]),
                risk_score=float(signal["risk_score"]),
                snippet=str(analysis["slot"].get("change", ""))[:200],
                source=str(analysis["doc_name"]),
                evidence_timestamp=_to_iso(_utc_now()),
                linked_node=payload.linked_node or payload.target,
                write_event=write_lifecycle_event,
            )
            if pending is not None:
                pending_messages.append(pending.id)

        findings = analysis.get("human_findings", [])
        _save_system_message(
            session=session,
            content="\n".join(["Grove 분석 완료", *findings]) if findings else "Grove 분석 완료",
            context_tag="forest:grove",
            linked_node=payload.linked_node or payload.target,
        )

        risk_score = 0.0
        signals = analysis.get("signals", [])
        if isinstance(signals, list) and signals:
            risk_score = max(float(item.get("risk_score", 0.0)) for item in signals if isinstance(item, dict))
        slot = analysis.get("slot", {})
        append_system_note(
            db=session,
            note_type="GROVE_SUMMARY",
            source_events=["GROVE_ANALYZED"],
            summary=f"{payload.target}에 대한 Grove 분석이 완료되었습니다.",
            body_markdown="\n".join(
                [
                    f"- doc: {analysis.get('doc_name', payload.doc_name)}",
                    f"- target: {payload.target}",
                    f"- slot_status: {slot.get('status', '')}",
                    f"- signals: {len(signals)}",
                ]
            ),
            status="ACTIVE",
            actionables=[
                {"type": "open_canopy", "project": safe_project},
                {"type": "review_questions", "target": payload.target},
            ],
            linked_cluster_id=str(signals[0].get("cluster_id")) if signals and isinstance(signals[0], dict) else None,
            risk_score=risk_score,
            badge="RISK_HIGH" if risk_score >= 0.8 else "INFO",
            dedup_key=f"grove:{safe_project}:{analysis.get('doc_name', payload.doc_name)}:{payload.target}:{slot.get('status', '')}",
        )

        ingest_trigger_event(
            session,
            event_type="GROVE_ANALYZED",
            payload={
                "project": safe_project,
                "target": payload.target,
                "missing_slots": len(signals),
                "risk_score": risk_score,
                "signals": len(signals),
            },
        )
        diary_payload = maybe_build_daily_diary(session)
        if diary_payload is not None:
            append_system_note(
                db=session,
                note_type=str(diary_payload["note_type"]),
                source_events=list(diary_payload["source_events"]),
                summary=str(diary_payload["summary"]),
                body_markdown=str(diary_payload["body_markdown"]),
                status=str(diary_payload["status"]),
                actionables=list(diary_payload["actionables"]),
                badge=str(diary_payload["badge"]),
                dedup_key=str(diary_payload["dedup_key"]),
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="ANALYSIS",
        target=payload.target,
        summary=f"{analysis['doc_name']} analyzed",
        payload={"signals": len(analysis.get("signals", [])), "slot_status": analysis["slot"].get("status")},
    )
    write_lifecycle_event(
        "FOREST_ANALYSIS",
        {
            "project": safe_project,
            "target": payload.target,
            "source_doc": analysis["doc_name"],
            "signals": len(analysis.get("signals", [])),
        },
        skill_id="forest.grove",
    )

    return {
        "status": "ok",
        "project": safe_project,
        "doc_path": analysis["paths"]["doc_path"],
        "analysis": {
            "last_delta": analysis["paths"]["last_delta"],
            "dependency_graph": analysis["paths"]["dependency_graph"],
            "risk_snapshot": analysis["paths"]["risk_snapshot"],
        },
        "human_findings": analysis.get("human_findings", []),
        "signals_created": analysis.get("signals", []),
        "forest_input_policy": "api_only",
    }


@router.post("/projects/{project_name}/grove/analyze/path")
async def grove_analyze_path(project_name: str, payload: GroveAnalyzePathRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    source_path = _resolve_grove_source_path(project_name=safe_project, raw_path=payload.path)
    try:
        content = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = source_path.read_text(encoding="utf-8", errors="replace")

    response = await grove_analyze(
        safe_project,
        GroveAnalyzeRequest(
            doc_name=source_path.name,
            content=content,
            target=payload.target,
            change=payload.change,
            scope=payload.scope,
            linked_node=payload.linked_node,
        ),
    )
    if isinstance(response, dict):
        response["source_path"] = str(source_path)
    return response


@router.post("/projects/{project_name}/work/generate")
async def generate_work_package(project_name: str, payload: GenerateWorkPackageRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    session = session_factory()
    try:
        _enforce_focus_lock_for_work_mutation(
            session=session,
            project_name=safe_project,
            operation="forest.work.generate",
        )
        required = [item.strip() for item in payload.required if item.strip()]
        if not required:
            required = ["요구사항 정리", "완료 JSON 보고 제출"]
        deliverables = [item.strip() for item in payload.deliverables if item.strip()]
        if not deliverables:
            deliverables = ["return_payload.json"]

        package_id = f"wp_{uuid4().hex}"
        title = payload.title.strip() if isinstance(payload.title, str) and payload.title.strip() else f"{payload.kind}:{payload.issue[:40]}"
        context_tag = _normalize_context_tag(payload.context_tag)
        work_packet = {
            "id": package_id,
            "kind": payload.kind,
            "context_tag": context_tag,
            "linked_node": payload.linked_node,
            "title": title,
            "issue": payload.issue,
            "acceptance_criteria": required,
            "deliverables": deliverables,
            "return_payload_spec": payload.return_payload_spec,
        }

        row = WorkPackage(
            id=package_id,
            title=title,
            description=payload.issue,
            payload={"work_packet": work_packet, "project": safe_project},
            context_tag=context_tag,
            status="READY",
            linked_node=payload.linked_node,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(row)

        work_dir = get_project_root(safe_project) / "work"
        filename = _next_work_filename(work_dir)
        md_path = work_dir / filename
        md_path.write_text(_render_work_markdown(work_packet), encoding="utf-8")

        _save_system_message(
            session=session,
            content=build_notice("notice.ide_ready"),
            context_tag="work",
            linked_node=payload.linked_node,
        )
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="WORK_PACKAGE_CREATED",
        target=package_id,
        summary=f"work package created: {title}",
    )
    write_lifecycle_event(
        "WORK_PACKAGE_CREATED",
        {"project": safe_project, "work_package_id": package_id, "kind": payload.kind},
        skill_id="forest.work",
    )
    roadmap_live = _record_live_roadmap_entry(
        project_name=safe_project,
        title=f"[forest] {title} 생성",
        summary=f"{payload.kind} work package 생성 · context={context_tag}",
        category="FEATURE_ADD",
        tags=["forest", "work", "live"],
        note=f"work_package_id:{package_id}",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "work_package_id": package_id,
        "md_path": str(md_path),
        "roadmap_live_record": {
            "recorded": int(roadmap_live.get("recorded", 0) or 0),
            "skipped": int(roadmap_live.get("skipped", 0) or 0),
        },
    }


@router.post("/projects/{project_name}/work/seed-from-inventory")
async def seed_work_from_inventory(project_name: str, payload: SeedInventoryWorkRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    include_statuses = {str(item).strip().upper() for item in (payload.include_statuses or []) if str(item).strip()}
    include_statuses = {item for item in include_statuses if item in {"READY", "IN_PROGRESS", "BLOCKED"}}
    if not include_statuses:
        include_statuses = {"READY", "IN_PROGRESS", "BLOCKED"}

    session = session_factory()
    try:
        _enforce_focus_lock_for_work_mutation(
            session=session,
            project_name=safe_project,
            operation="forest.work.seed_inventory",
        )
        seeded = _seed_work_from_inventory_internal(
            session=session,
            project_name=safe_project,
            include_statuses=include_statuses,
            limit=int(payload.limit),
            force=bool(payload.force),
        )
        created = list(seeded.get("created", []))
        skipped_existing = int(seeded.get("skipped_existing", 0) or 0)
        skipped_limit = int(seeded.get("skipped_limit", 0) or 0)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    summary_text = f"system inventory work seed created={len(created)} skipped={skipped_existing}"
    append_project_ledger_event(
        project_name=safe_project,
        event_type="WORK_PACKAGE_CREATED",
        target=f"inventory:{safe_project}",
        summary=summary_text,
        payload={
            "created_count": len(created),
            "skipped_existing": skipped_existing,
            "skipped_limit": skipped_limit,
        },
    )
    write_lifecycle_event(
        "WORK_PACKAGE_CREATED",
        {
            "project": safe_project,
            "source": "system_inventory",
            "created_count": len(created),
            "skipped_existing": skipped_existing,
            "skipped_limit": skipped_limit,
        },
        skill_id="forest.work",
    )
    roadmap_live = _record_live_roadmap_entry(
        project_name=safe_project,
        title="[forest] 시스템 인벤토리 작업 시드",
        summary=f"created={len(created)} skipped={skipped_existing} limit={int(payload.limit)}",
        category="FEATURE_ADD",
        tags=["forest", "work", "inventory", "live"],
        note="source:system_inventory",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "created_count": len(created),
        "skipped_existing": skipped_existing,
        "skipped_limit": skipped_limit,
        "items": created,
        "roadmap_live_record": {
            "recorded": int(roadmap_live.get("recorded", 0) or 0),
            "skipped": int(roadmap_live.get("skipped", 0) or 0),
        },
    }


@router.get("/projects/{project_name}/ideas")
async def list_frozen_ideas(
    project_name: str,
    status: Literal["all", "frozen", "promoted", "discarded"] = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=500),
):
    safe_project = sanitize_project_name(project_name)
    session = session_factory()
    try:
        project_tag = f"project:{safe_project}"
        rows = (
            session.query(MindItem)
            .filter(
                MindItem.type == "FOCUS",
            )
            .order_by(MindItem.updated_at.desc(), MindItem.id.asc())
            .limit(max(limit * 4, 200))
            .all()
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            tags = [str(tag).strip().lower() for tag in (row.tags or []) if str(tag).strip()]
            if "freeze" not in tags or project_tag not in tags:
                continue
            item = _serialize_idea(row)
            item_status = str(item.get("status", "")).lower()
            if status != "all" and item_status != status:
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return {"status": "ok", "project": safe_project, "items": items}
    finally:
        session.close()


@router.post("/projects/{project_name}/ideas/freeze")
async def freeze_idea(project_name: str, payload: FreezeIdeaRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    session = session_factory()
    try:
        tag = _normalize_idea_tag(payload.tag)
        project_tag = f"project:{safe_project}"
        now = _utc_now()
        daily_limit = max(1, int(getattr(settings, "forest_freeze_daily_limit", 10) or 10))

        existing = (
            session.query(MindItem)
            .filter(
                MindItem.type == "FOCUS",
                MindItem.status == "parked",
            )
            .order_by(MindItem.created_at.desc(), MindItem.id.asc())
            .limit(500)
            .all()
        )
        today = now.date().isoformat()
        today_count = 0
        for row in existing:
            tags = [str(item).strip().lower() for item in (row.tags or []) if str(item).strip()]
            if "freeze" not in tags or project_tag not in tags:
                continue
            created = _to_iso(row.created_at)
            if created.startswith(today):
                today_count += 1
        if today_count >= daily_limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "FREEZE_DAILY_LIMIT",
                    "project": safe_project,
                    "daily_limit": daily_limit,
                    "today_count": today_count,
                },
            )

        idea_id = f"idea:{safe_project}:{uuid4().hex}"
        row = MindItem(
            id=idea_id,
            type="FOCUS",
            title=payload.title.strip(),
            summary_120=f"Frozen idea · {payload.title.strip()[:88]}",
            priority=10,
            risk_score=0.0,
            confidence=0.6,
            linked_bits=[],
            tags=["freeze", project_tag, f"idea_tag:{tag}", "freeze_status:frozen"],
            source_events=["IDEA_FROZEN"],
            status="parked",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        _save_system_message(
            session=session,
            content=f"주인님, 아이디어를 Freeze 보관함에 격리했습니다: {payload.title.strip()}",
            context_tag="forest:canopy",
            linked_node="forest:focus",
        )
        session.commit()
        serialized = _serialize_idea(row)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="IDEA_FROZEN",
        target=serialized["idea_id"],
        summary=f"frozen idea: {serialized['title']}",
        payload={"tag": serialized["tag"]},
    )
    write_lifecycle_event(
        "IDEA_FROZEN",
        {"project": safe_project, "idea_id": serialized["idea_id"], "tag": serialized["tag"]},
        skill_id="forest.focus",
    )
    return {"status": "ok", "project": safe_project, "idea": serialized}


@router.post("/projects/{project_name}/ideas/{idea_id}/promote")
async def promote_frozen_idea(project_name: str, idea_id: str, payload: PromoteIdeaRequest):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    session = session_factory()
    try:
        _enforce_focus_lock_for_work_mutation(
            session=session,
            project_name=safe_project,
            operation="forest.idea.promote",
        )
        project_tag = f"project:{safe_project}"
        row = session.query(MindItem).filter(MindItem.id == idea_id, MindItem.type == "FOCUS").one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
        tags = [str(tag).strip().lower() for tag in (row.tags or []) if str(tag).strip()]
        if "freeze" not in tags or project_tag not in tags:
            raise HTTPException(status_code=404, detail=f"idea not found: {idea_id}")
        if "freeze_status:promoted" in tags:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEA_ALREADY_PROMOTED", "idea_id": idea_id},
            )

        updated_tags = [tag for tag in tags if not tag.startswith("freeze_status:")]
        updated_tags.append("freeze_status:promoted")
        row.tags = sorted(set(updated_tags))
        row.status = "active"
        row.summary_120 = f"Promoted idea · {row.title[:84]}"
        linked_bits = [str(item).strip() for item in (row.linked_bits or []) if str(item).strip()]
        linked_bits = [item for item in linked_bits if not item.startswith("north_star:") and not item.startswith("proof_48h:")]
        linked_bits.append(f"north_star:{payload.north_star_link.strip()}")
        linked_bits.append(f"proof_48h:{payload.proof_48h.strip()}")
        row.linked_bits = linked_bits
        source_events = [str(item).strip() for item in (row.source_events or []) if str(item).strip()]
        if "IDEA_PROMOTED" not in source_events:
            source_events.append("IDEA_PROMOTED")
        row.source_events = source_events
        row.updated_at = _utc_now()
        session.add(row)

        created_work: dict[str, Any] | None = None
        if payload.promote_to_work:
            package_id = f"wp_{uuid4().hex}"
            work_context_tag = _normalize_context_tag(payload.work_context_tag)
            work_kind = str(payload.work_kind or "IMPLEMENT").strip().upper()
            if work_kind not in {"ANALYZE", "IMPLEMENT", "REVIEW", "MIGRATE"}:
                work_kind = "IMPLEMENT"
            work_title = f"[IDEA] {row.title}"
            work_packet = _build_work_packet_from_idea(
                package_id=package_id,
                title=work_title,
                issue=f"Freeze 승격 아이디어 실행: {row.title}",
                kind=work_kind,
                context_tag=work_context_tag,
                linked_node=row.id,
                north_star_link=payload.north_star_link,
                proof_48h=payload.proof_48h,
            )
            work_row = WorkPackage(
                id=package_id,
                title=work_title,
                description=f"Freeze 아이디어 승격: {row.title}",
                payload={"work_packet": work_packet, "project": safe_project, "source": "idea_promote", "idea_id": row.id},
                context_tag=work_context_tag,
                status="READY",
                linked_node=row.id,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(work_row)
            work_dir = get_project_root(safe_project) / "work"
            filename = _next_work_filename(work_dir)
            md_path = work_dir / filename
            md_path.write_text(_render_work_markdown(work_packet), encoding="utf-8")
            created_work = {
                "work_package_id": package_id,
                "md_path": str(md_path),
                "kind": work_kind,
                "context_tag": work_context_tag,
            }
        _save_system_message(
            session=session,
            content=(
                f"주인님, Freeze 아이디어를 승격했습니다: {row.title}\n"
                f"{'Work 패키지도 생성했습니다.' if created_work else '승격만 반영했고 Work 생성은 보류했습니다.'}"
            ),
            context_tag="forest:canopy",
            linked_node="forest:focus",
        )
        session.commit()
        serialized = _serialize_idea(row)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="IDEA_PROMOTED",
        target=serialized["idea_id"],
        summary=f"promoted idea: {serialized['title']}",
        payload={"tag": serialized["tag"]},
    )
    if payload.promote_to_work and created_work is not None:
        append_project_ledger_event(
            project_name=safe_project,
            event_type="WORK_PACKAGE_CREATED",
            target=str(created_work["work_package_id"]),
            summary=f"work package created from promoted idea: {serialized['title']}",
            payload={"source": "IDEA_PROMOTED", "idea_id": serialized["idea_id"]},
        )
        write_lifecycle_event(
            "WORK_PACKAGE_CREATED",
            {
                "project": safe_project,
                "work_package_id": str(created_work["work_package_id"]),
                "kind": str(created_work["kind"]),
                "source": "IDEA_PROMOTED",
            },
            skill_id="forest.work",
        )
    write_lifecycle_event(
        "IDEA_PROMOTED",
        {"project": safe_project, "idea_id": serialized["idea_id"], "tag": serialized["tag"]},
        skill_id="forest.focus",
    )
    return {"status": "ok", "project": safe_project, "idea": serialized, "work": created_work}


@router.post("/projects/{project_name}/roots/export")
async def export_roots(project_name: str):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    root = get_project_root(safe_project)

    session = session_factory()
    try:
        question_rows = (
            session.query(QuestionPool)
            .order_by(QuestionPool.risk_score.desc(), QuestionPool.hit_count.desc(), QuestionPool.cluster_id.asc())
            .all()
        )
        question_pool = [
            {
                "cluster_id": row.cluster_id,
                "description": row.description,
                "hit_count": int(row.hit_count or 0),
                "risk_score": float(row.risk_score or 0.0),
                "status": row.status,
                "linked_nodes": row.linked_nodes or [],
                "evidence": row.evidence or [],
                "last_triggered_at": _to_iso(row.last_triggered_at),
                "last_asked_at": _to_iso(row.last_asked_at),
                "asked_count": int(row.asked_count or 0),
            }
            for row in question_rows
        ]
        write_json(root / "questions" / "question_pool.json", {"items": question_pool})

        work_rows = session.query(WorkPackage).order_by(WorkPackage.created_at.asc(), WorkPackage.id.asc()).all()
        exported_work = []
        for idx, row in enumerate(work_rows, start=1):
            payload_obj = row.payload if isinstance(row.payload, dict) else {}
            packet = payload_obj.get("work_packet") if isinstance(payload_obj, dict) else None
            if not isinstance(packet, dict):
                packet = {
                    "id": row.id,
                    "context_tag": row.context_tag,
                    "linked_node": row.linked_node,
                    "issue": row.description or row.title,
                    "acceptance_criteria": [],
                    "deliverables": [],
                }
            packet["title"] = row.title
            if "issue" not in packet:
                packet["issue"] = row.description or row.title
            filename = f"package_{idx:03d}.md"
            md_path = root / "work" / filename
            md_path.write_text(_render_work_markdown(packet), encoding="utf-8")
            exported_work.append({"id": row.id, "path": str(md_path), "status": row.status, "report_status": _extract_report_status(row)})

        status_snapshot = {
            "generated_at": _to_iso(_utc_now()),
            "questions": len(question_pool),
            "work_packages": len(exported_work),
            "done": sum(1 for row in exported_work if row["report_status"] == "DONE"),
            "blocked": sum(1 for row in exported_work if row["report_status"] == "BLOCKED"),
            "failed": sum(1 for row in exported_work if row["report_status"] == "FAILED"),
            "ready": sum(1 for row in exported_work if not row["report_status"]),
        }
        write_json(root / "status" / "roots_snapshot.json", status_snapshot)
        write_json(
            root / "status" / "export_meta.json",
            {
                "exported_at": _to_iso(_utc_now()),
                "source": "DB",
                "note": "Forest is read-only export view",
            },
        )
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="ROOTS_EXPORT",
        target=safe_project,
        summary=f"roots exported: questions={len(question_pool)}, work={len(exported_work)}",
    )
    write_lifecycle_event(
        "FOREST_ROOTS_EXPORTED",
        {"project": safe_project, "questions": len(question_pool), "work_packages": len(exported_work)},
        skill_id="forest.roots",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "questions_path": str(root / "questions" / "question_pool.json"),
        "work_dir": str(root / "work"),
        "status_path": str(root / "status" / "roots_snapshot.json"),
        "export_meta_path": str(root / "status" / "export_meta.json"),
        "questions": len(question_pool),
        "work_packages": len(exported_work),
        "forest_input_policy": "api_only",
    }


@router.get("/projects/{project_name}/canopy/data")
async def canopy_data(
    project_name: str,
    view: Literal["focus", "overview"] = Query(default="focus"),
    risk_threshold: float = Query(default=0.8, ge=0.0, le=1.0),
    module_sort: Literal["importance", "progress", "risk"] = Query(default="importance"),
    event_filter: Literal["all", "analysis", "work", "canopy", "question", "bitmap"] = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    module: Literal["all", "chat", "note", "editor", "subtitle", "forest", "core"] = Query(default="all"),
):
    safe_project = sanitize_project_name(project_name)
    session = session_factory()
    try:
        data = build_canopy_data(
            project_name=safe_project,
            session=session,
            view=view,
            risk_threshold=risk_threshold,
            module_sort=module_sort,
            event_filter=event_filter,
            limit=limit,
            offset=offset,
            module_filter=module,
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        )
    finally:
        session.close()
    return {"status": "ok", **data}


@router.get("/projects/{project_name}/spec/index")
async def spec_index(project_name: str, limit: int = Query(default=200, ge=1, le=500)):
    safe_project = sanitize_project_name(project_name)
    rows = _build_spec_index(project_name=safe_project, limit=limit)
    return {
        "status": "ok",
        "project": safe_project,
        "total": len(rows),
        "items": rows,
    }


@router.get("/projects/{project_name}/spec/read")
async def spec_read(
    project_name: str,
    path: str = Query(min_length=1, max_length=400),
    max_chars: int = Query(default=12000, ge=2000, le=80000),
):
    safe_project = sanitize_project_name(project_name)
    target = _resolve_doc_path(safe_project, path)
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target.read_text(encoding="utf-8", errors="replace")
    truncated = False
    if len(content) > max_chars:
        content = content[: max(1, int(max_chars))]
        truncated = True
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(target),
        "title": _read_doc_title(target),
        "content": content,
        "truncated": truncated,
    }


@router.post("/projects/{project_name}/spec/upload")
async def spec_upload(project_name: str, payload: SpecUploadRequest):
    safe_project = sanitize_project_name(project_name)
    owner = str(payload.owner or "").strip().lower() or "user"
    lane = str(payload.lane or "").strip().lower() or owner
    note = str(payload.note or "").strip() or "spec uploaded"
    file_name = _sanitize_upload_filename(payload.file_name)
    target = _next_available_doc_path(safe_project, file_name)
    target.write_text(str(payload.content), encoding="utf-8")

    doc_type = str(payload.doc_type or "spec").strip().lower() or "spec"
    tags = [
        "spec",
        "upload",
        f"doc_type:{doc_type}",
        "review_state:pending",
        f"owner:{owner}",
        f"lane:{lane}",
        "scope:project",
        f"spec_ref:{target}",
    ]
    sync_result = sync_roadmap_entries(
        project_name=safe_project,
        items=[
            {
                "title": f"명세 업로드: {target.name}",
                "summary": note,
                "files": [str(target)],
                "spec_refs": [str(target)],
                "tags": tags,
                "category": "FEATURE_ADD",
                "note": "spec_upload",
                "owner": owner,
                "lane": lane,
                "scope": "project",
                "review_state": "pending",
            }
        ],
        force_record=False,
        entry_type="SYNC_CHANGE",
    )
    append_project_ledger_event(
        project_name=safe_project,
        event_type="SPEC_UPLOADED",
        target=str(target),
        summary=f"spec uploaded by {owner}",
        payload={
            "path": str(target),
            "owner": owner,
            "lane": lane,
            "recorded": int(sync_result.get("recorded", 0) or 0),
            "skipped": int(sync_result.get("skipped", 0) or 0),
        },
    )
    write_lifecycle_event(
        "FOREST_SPEC_UPLOADED",
        {
            "project": safe_project,
            "path": str(target),
            "owner": owner,
            "lane": lane,
        },
        skill_id="forest.spec",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(target),
        "doc_type": doc_type,
        "recorded": int(sync_result.get("recorded", 0) or 0),
        "skipped": int(sync_result.get("skipped", 0) or 0),
    }


@router.post("/projects/{project_name}/spec/status")
async def spec_status(project_name: str, payload: SpecStatusUpdateRequest):
    safe_project = sanitize_project_name(project_name)
    target = _resolve_doc_path(safe_project, payload.path)
    owner = str(payload.owner or "").strip().lower() or "codex"
    lane = str(payload.lane or "").strip().lower() or owner
    status = _normalize_spec_status(payload.status)
    note = str(payload.note or "").strip() or f"spec status -> {status}"
    category = "SYSTEM_CHANGE" if status == "confirmed" else "PROBLEM_FIX" if status == "review" else "FEATURE_ADD"
    tags = [
        "spec",
        "status_update",
        f"review_state:{status}",
        f"owner:{owner}",
        f"lane:{lane}",
        "scope:project",
        f"spec_ref:{target}",
    ]
    sync_result = sync_roadmap_entries(
        project_name=safe_project,
        items=[
            {
                "title": f"명세 상태 변경: {target.name}",
                "summary": note,
                "files": [str(target)],
                "spec_refs": [str(target)],
                "tags": tags,
                "category": category,
                "note": "spec_status_update",
                "owner": owner,
                "lane": lane,
                "scope": "project",
                "review_state": status,
            }
        ],
        force_record=False,
        entry_type="SYNC_CHANGE",
    )
    append_project_ledger_event(
        project_name=safe_project,
        event_type="SPEC_STATUS_UPDATED",
        target=str(target),
        summary=f"spec status {status} by {owner}",
        payload={"status": status, "owner": owner, "lane": lane},
    )
    write_lifecycle_event(
        "FOREST_SPEC_STATUS_UPDATED",
        {"project": safe_project, "path": str(target), "status": status, "owner": owner, "lane": lane},
        skill_id="forest.spec",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(target),
        "review_state": status,
        "recorded": int(sync_result.get("recorded", 0) or 0),
        "skipped": int(sync_result.get("skipped", 0) or 0),
    }


@router.post("/projects/{project_name}/spec/review-run")
async def spec_review_run(project_name: str, payload: SpecSonEReviewRequest):
    safe_project = sanitize_project_name(project_name)
    target_path = _resolve_doc_path(safe_project, payload.path)
    owner = str(payload.owner or "").strip().lower() or "codex"
    lane = str(payload.lane or "").strip().lower() or owner
    note = str(payload.note or "").strip() or "spec SonE review run"
    try:
        content = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = target_path.read_text(encoding="utf-8", errors="replace")
    result = analyze_to_forest(
        project_name=safe_project,
        doc_name=target_path.name,
        content=content,
        target=str(payload.target or "spec-module"),
        change=str(payload.change or "명세 검토"),
        scope=payload.scope,
        write_doc=False,
    )
    risk_snapshot = result.get("risk_snapshot") if isinstance(result.get("risk_snapshot"), dict) else {}
    clusters = risk_snapshot.get("clusters") if isinstance(risk_snapshot.get("clusters"), list) else []
    max_risk = 0.0
    for row in clusters:
        if not isinstance(row, dict):
            continue
        max_risk = max(max_risk, float(row.get("risk_score", 0.0) or 0.0))
    missing_slots = result.get("missing_slots") if isinstance(result.get("missing_slots"), list) else []
    status = "review"
    if max_risk < 0.5 and not missing_slots:
        status = "confirmed"
    summary = note
    if missing_slots:
        summary = f"{note} · missing_slots={len(missing_slots)} · max_risk={max_risk:.2f}"
    tags = [
        "spec",
        "sone_review",
        f"review_state:{status}",
        f"owner:{owner}",
        f"lane:{lane}",
        "scope:project",
        f"spec_ref:{target_path}",
    ]
    sync_result = sync_roadmap_entries(
        project_name=safe_project,
        items=[
            {
                "title": f"명세 SonE 검토: {target_path.name}",
                "summary": summary,
                "files": [str(target_path)],
                "spec_refs": [str(target_path)],
                "tags": tags,
                "category": "PROBLEM_FIX" if status == "review" else "SYSTEM_CHANGE",
                "note": "spec_sone_review",
                "owner": owner,
                "lane": lane,
                "scope": "project",
                "review_state": status,
            }
        ],
        force_record=False,
        entry_type="SYNC_CHANGE",
    )
    append_project_ledger_event(
        project_name=safe_project,
        event_type="SPEC_SONE_REVIEWED",
        target=str(target_path),
        summary=f"spec SonE reviewed by {owner}",
        payload={
            "review_state": status,
            "max_risk": float(max_risk),
            "missing_slots": len(missing_slots),
            "recorded": int(sync_result.get("recorded", 0) or 0),
            "skipped": int(sync_result.get("skipped", 0) or 0),
        },
    )
    write_lifecycle_event(
        "FOREST_SPEC_SONE_REVIEWED",
        {
            "project": safe_project,
            "path": str(target_path),
            "review_state": status,
            "max_risk": float(max_risk),
            "missing_slots": len(missing_slots),
        },
        skill_id="forest.spec",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(target_path),
        "review_state": status,
        "max_risk": float(max_risk),
        "missing_slots": missing_slots,
        "clusters": clusters,
        "recorded": int(sync_result.get("recorded", 0) or 0),
        "skipped": int(sync_result.get("skipped", 0) or 0),
    }


@router.post("/projects/{project_name}/roadmap/record")
async def record_roadmap_snapshot(project_name: str, payload: RoadmapRecordRequest | None = None):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    session = session_factory()
    try:
        data = build_canopy_data(
            project_name=safe_project,
            session=session,
            view="focus",
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        )
    finally:
        session.close()

    human_view = data.get("human_view") if isinstance(data.get("human_view"), dict) else {}
    summary_cards = human_view.get("summary_cards") if isinstance(human_view.get("summary_cards"), list) else []
    quick_lists = human_view.get("quick_lists") if isinstance(human_view.get("quick_lists"), dict) else {}
    roadmap_now = human_view.get("roadmap_now") if isinstance(human_view.get("roadmap_now"), dict) else {}
    note_text = str((payload.note if payload is not None else "") or "").strip()
    title_text = str((payload.title if payload is not None else "") or "").strip()
    summary_text = str((payload.summary if payload is not None else "") or "").strip()
    files = [
        str(row).strip()
        for row in ((payload.files if payload is not None else []) or [])
        if str(row).strip()
    ]
    spec_refs = [
        str(row).strip()
        for row in ((payload.spec_refs if payload is not None else []) or [])
        if str(row).strip()
    ]
    tags = [
        str(row).strip()
        for row in ((payload.tags if payload is not None else []) or [])
        if str(row).strip()
    ]
    category_hint = str((payload.category if payload is not None else "") or "").strip()
    phase_text = str((payload.phase if payload is not None else "") or "").strip()
    phase_step_text = str((payload.phase_step if payload is not None else "") or "").strip()
    phase_title_text = str((payload.phase_title if payload is not None else "") or "").strip()
    owner_text = str((payload.owner if payload is not None else "") or "").strip().lower()
    lane_text = str((payload.lane if payload is not None else "") or "").strip().lower()
    scope_text = str((payload.scope if payload is not None else "") or "").strip().lower()
    review_state_text = str((payload.review_state if payload is not None else "") or "").strip().lower()
    force_record = bool((payload.force_record if payload is not None else False) or False)

    if not phase_text:
        for tag in tags:
            raw = str(tag).strip()
            if raw.lower().startswith("phase:"):
                phase_text = raw.split(":", 1)[1].strip()
                break
    if not phase_step_text:
        for tag in tags:
            raw = str(tag).strip()
            if raw.lower().startswith("phase_step:"):
                phase_step_text = raw.split(":", 1)[1].strip()
                break
    if phase_text and not phase_step_text:
        phase_step_text = f"{phase_text}.0"
    if owner_text and not any(str(tag).lower().startswith("owner:") for tag in tags):
        tags.append(f"owner:{owner_text}")
    if lane_text and not any(str(tag).lower().startswith("lane:") for tag in tags):
        tags.append(f"lane:{lane_text}")
    if scope_text and not any(str(tag).lower().startswith("scope:") for tag in tags):
        tags.append(f"scope:{scope_text}")
    if review_state_text and not any(str(tag).lower().startswith("review_state:") for tag in tags):
        tags.append(f"review_state:{review_state_text}")
    for ref in spec_refs:
        tag = f"spec_ref:{ref}"
        if not any(str(existing).strip().lower() == tag.lower() for existing in tags):
            tags.append(tag)

    if not title_text:
        current_id = str(roadmap_now.get("current_mission_id", "")).strip()
        title_text = f"focus snapshot: {current_id or 'none'}"
    if not summary_text:
        summary_text = " | ".join(
            [
                str(((summary_cards[0] if len(summary_cards) > 0 else {}) or {}).get("text", "")).strip(),
                str(((summary_cards[1] if len(summary_cards) > 1 else {}) or {}).get("text", "")).strip(),
                str(((summary_cards[2] if len(summary_cards) > 2 else {}) or {}).get("text", "")).strip(),
            ]
        ).strip(" |")
        if not summary_text:
            summary_text = str(roadmap_now.get("next_action", "")).strip() or "focus snapshot"

    category, category_reason = classify_record_entry(
        title=title_text,
        summary=summary_text,
        files=files,
        tags=tags,
        category_hint=category_hint or "SYSTEM_CHANGE",
    )
    if not should_record_entry(category, force=force_record):
        return {
            "status": "ok",
            "project": safe_project,
            "path": str(get_project_root(safe_project) / "status" / "roadmap_journal.jsonl"),
            "recorded": 0,
            "skipped": 1,
            "recorded_items": [],
            "skipped_items": [{"title": title_text, "category": category, "reason": f"policy_skip:{category}"}],
            "policy": {
                "tracked_categories": ["SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"],
                "force_record": bool(force_record),
            },
            "entry": {
                "project": safe_project,
                "title": title_text,
                "summary": summary_text,
                "category": category,
                "category_reason": category_reason,
                "phase": phase_text,
                "phase_step": phase_step_text,
                "phase_title": phase_title_text,
                "owner": owner_text,
                "lane": lane_text,
                "scope": scope_text,
                "review_state": review_state_text,
                "spec_refs": spec_refs,
                "note": note_text,
                "summary_cards": summary_cards,
                "roadmap_now": roadmap_now,
            },
        }

    entry = {
        "recorded_at": _to_iso(_utc_now()),
        "project": safe_project,
        "type": "FOCUS_SNAPSHOT",
        "title": title_text,
        "summary": summary_text,
        "files": files,
        "tags": tags,
        "category": category,
        "category_reason": category_reason,
        "phase": phase_text,
        "phase_step": phase_step_text,
        "phase_title": phase_title_text,
        "owner": owner_text,
        "lane": lane_text,
        "scope": scope_text,
        "review_state": review_state_text,
        "spec_refs": spec_refs,
        "summary_cards": summary_cards,
        "roadmap_now": roadmap_now,
        "pending_top": quick_lists.get("pending_top", []),
        "risk_top": quick_lists.get("risk_top", []),
        "recent_top": quick_lists.get("recent_top", []),
        "note": note_text,
    }
    status_dir = get_project_root(safe_project) / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    journal_path = status_dir / "roadmap_journal.jsonl"
    fingerprint = make_record_fingerprint(
        project=safe_project,
        category=category,
        title=title_text,
        summary=summary_text,
        files=files,
    )
    entry["fingerprint"] = fingerprint
    existing_fingerprints = _read_recent_fingerprints(journal_path, limit=500)
    if fingerprint in existing_fingerprints:
        return {
            "status": "ok",
            "project": safe_project,
            "path": str(journal_path),
            "recorded": 0,
            "skipped": 1,
            "recorded_items": [],
            "skipped_items": [{"title": title_text, "category": category, "reason": "duplicate"}],
            "policy": {
                "tracked_categories": ["SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"],
                "force_record": bool(force_record),
            },
            "entry": entry,
        }

    with journal_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    append_project_ledger_event(
        project_name=safe_project,
        event_type="ROADMAP_RECORDED",
        target=safe_project,
        summary=f"focus roadmap snapshot recorded ({category})",
        payload={
            "path": str(journal_path),
            "remaining_work": int(roadmap_now.get("remaining_work", 0) or 0),
            "category": category,
            "phase": phase_text,
            "phase_step": phase_step_text,
        },
    )
    write_lifecycle_event(
        "FOREST_ROADMAP_RECORDED",
        {
            "project": safe_project,
            "path": str(journal_path),
            "remaining_work": int(roadmap_now.get("remaining_work", 0) or 0),
            "high_risk_count": int(roadmap_now.get("high_risk_count", 0) or 0),
            "category": category,
            "phase": phase_text,
            "phase_step": phase_step_text,
        },
        skill_id="forest.roadmap",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(journal_path),
        "recorded": 1,
        "skipped": 0,
        "recorded_items": [
            {
                "title": title_text,
                "summary": summary_text,
                "files": files,
                "tags": tags,
                "category": category,
                "category_reason": category_reason,
                "phase": phase_text,
                "phase_step": phase_step_text,
                "phase_title": phase_title_text,
                "owner": owner_text,
                "lane": lane_text,
                "scope": scope_text,
                "review_state": review_state_text,
                "spec_refs": spec_refs,
                "fingerprint": fingerprint,
            }
        ],
        "skipped_items": [],
        "policy": {
            "tracked_categories": ["SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"],
            "force_record": bool(force_record),
        },
        "entry": entry,
    }


@router.post("/projects/{project_name}/spec/review-request")
async def request_spec_review(project_name: str, payload: SpecReviewRequest):
    safe_project = sanitize_project_name(project_name)
    target = _resolve_doc_path(safe_project, payload.path)
    owner = str(payload.owner or "").strip().lower() or "codex"
    lane = str(payload.lane or "").strip().lower() or owner
    note = str(payload.note or "").strip() or "spec review requested"
    title = f"명세 검토 요청: {target.name}"
    summary = note
    tags = [
        "spec",
        "review_request",
        f"owner:{owner}",
        f"lane:{lane}",
        "scope:project",
        "review_state:review_requested",
        f"spec_ref:{target}",
    ]
    sync_result = sync_roadmap_entries(
        project_name=safe_project,
        items=[
            {
                "title": title,
                "summary": summary,
                "files": [str(target)],
                "spec_refs": [str(target)],
                "tags": tags,
                "category": "SYSTEM_CHANGE",
                "note": "spec_review_request",
                "owner": owner,
                "lane": lane,
                "scope": "project",
                "review_state": "review_requested",
            }
        ],
        force_record=False,
        entry_type="SYNC_CHANGE",
    )
    append_project_ledger_event(
        project_name=safe_project,
        event_type="SPEC_REVIEW_REQUESTED",
        target=str(target),
        summary=f"spec review requested by {owner}",
        payload={
            "path": str(target),
            "owner": owner,
            "lane": lane,
            "recorded": int(sync_result.get("recorded", 0) or 0),
            "skipped": int(sync_result.get("skipped", 0) or 0),
        },
    )
    write_lifecycle_event(
        "FOREST_SPEC_REVIEW_REQUESTED",
        {
            "project": safe_project,
            "path": str(target),
            "owner": owner,
            "lane": lane,
            "recorded": int(sync_result.get("recorded", 0) or 0),
            "skipped": int(sync_result.get("skipped", 0) or 0),
        },
        skill_id="forest.spec",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "path": str(target),
        "recorded": int(sync_result.get("recorded", 0) or 0),
        "skipped": int(sync_result.get("skipped", 0) or 0),
        "recorded_items": sync_result.get("recorded_items", []),
        "skipped_items": sync_result.get("skipped_items", []),
    }


@router.get("/projects/{project_name}/todo")
async def get_project_todo(project_name: str):
    safe_project = sanitize_project_name(project_name)
    items = _sort_todo_items(_load_todo_items(safe_project))
    return {
        "status": "ok",
        "project": safe_project,
        "total": len(items),
        "items": items,
    }


@router.post("/projects/{project_name}/todo/upsert")
async def upsert_project_todo(project_name: str, payload: TodoUpsertRequest):
    safe_project = sanitize_project_name(project_name)
    items = _load_todo_items(safe_project)
    now_iso = _to_iso(_utc_now())
    row_id = str(payload.id or "").strip() or f"todo_{uuid4().hex}"
    status = _normalize_todo_status(payload.status)
    entry = {
        "id": row_id,
        "title": str(payload.title).strip(),
        "detail": str(payload.detail or "").strip(),
        "priority_weight": int(payload.priority_weight),
        "category": str(payload.category or "").strip(),
        "lane": str(payload.lane or "").strip().lower() or "general",
        "spec_ref": str(payload.spec_ref or "").strip(),
        "status": status,
        "checked": status == "done",
        "updated_at": now_iso,
    }
    found = False
    for idx, row in enumerate(items):
        if str(row.get("id", "")) == row_id:
            created_at = str(row.get("created_at", "")).strip() or now_iso
            entry["created_at"] = created_at
            items[idx] = {**row, **entry}
            found = True
            break
    if not found:
        entry["created_at"] = now_iso
        items.append(entry)

    items = _sort_todo_items(items)
    _save_todo_items(safe_project, items)
    append_project_ledger_event(
        project_name=safe_project,
        event_type="TODO_UPSERTED",
        target=row_id,
        summary=f"todo upsert ({status})",
        payload={
            "title": entry["title"],
            "priority_weight": int(entry["priority_weight"]),
            "lane": entry["lane"],
            "spec_ref": entry["spec_ref"],
        },
    )
    write_lifecycle_event(
        "FOREST_TODO_UPSERTED",
        {
            "project": safe_project,
            "todo_id": row_id,
            "status": status,
            "priority_weight": int(entry["priority_weight"]),
        },
        skill_id="forest.todo",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "item": entry,
        "total": len(items),
        "items": items,
    }


@router.post("/projects/{project_name}/todo/{item_id}/status")
async def update_project_todo_status(project_name: str, item_id: str, payload: TodoStatusRequest):
    safe_project = sanitize_project_name(project_name)
    target_id = str(item_id or "").strip()
    if not target_id:
        raise HTTPException(status_code=400, detail="todo id is required")
    items = _load_todo_items(safe_project)
    found = None
    now_iso = _to_iso(_utc_now())
    for row in items:
        if str(row.get("id", "")) != target_id:
            continue
        found = row
        if payload.status is not None:
            row["status"] = _normalize_todo_status(payload.status)
        if payload.checked is not None:
            row["checked"] = bool(payload.checked)
            if bool(payload.checked):
                row["status"] = "done"
        row["updated_at"] = now_iso
        if row.get("status") == "done":
            row["checked"] = True
        break
    if found is None:
        raise HTTPException(status_code=404, detail=f"todo not found: {target_id}")
    items = _sort_todo_items(items)
    _save_todo_items(safe_project, items)
    append_project_ledger_event(
        project_name=safe_project,
        event_type="TODO_STATUS_UPDATED",
        target=target_id,
        summary=f"todo status {found.get('status')}",
        payload={"checked": bool(found.get("checked")), "updated_at": now_iso},
    )
    write_lifecycle_event(
        "FOREST_TODO_STATUS_UPDATED",
        {"project": safe_project, "todo_id": target_id, "status": found.get("status"), "checked": bool(found.get("checked"))},
        skill_id="forest.todo",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "item": found,
        "total": len(items),
        "items": items,
    }


@router.post("/projects/{project_name}/roadmap/sync")
async def sync_roadmap_changes(project_name: str, payload: RoadmapSyncRequest):
    safe_project = sanitize_project_name(project_name)
    force_record = bool(payload.force_record)
    service_rows = [
        {
            "title": str(item.title or "").strip(),
            "summary": str(item.summary or "").strip(),
            "files": [str(row).strip() for row in item.files if str(row).strip()],
            "spec_refs": [str(row).strip() for row in item.spec_refs if str(row).strip()],
            "tags": [str(row).strip() for row in item.tags if str(row).strip()],
            "category": str(item.category or "").strip(),
            "note": str(item.note or "").strip(),
            "phase": str(item.phase or "").strip(),
            "phase_step": str(item.phase_step or "").strip(),
            "phase_title": str(item.phase_title or "").strip(),
            "owner": str(item.owner or "").strip().lower(),
            "lane": str(item.lane or "").strip().lower(),
            "scope": str(item.scope or "").strip().lower(),
            "review_state": str(item.review_state or "").strip().lower(),
        }
        for item in payload.items
    ]
    sync_result = sync_roadmap_entries(
        project_name=safe_project,
        items=service_rows,
        force_record=force_record,
        entry_type="SYNC_CHANGE",
    )
    journal_path = sync_result["path"]
    recorded_entries = sync_result["recorded_items"]
    skipped_items = sync_result["skipped_items"]

    append_project_ledger_event(
        project_name=safe_project,
        event_type="ROADMAP_SYNCED",
        target=safe_project,
        summary=f"sync roadmap recorded={len(recorded_entries)} skipped={len(skipped_items)}",
        payload={
            "received": len(payload.items),
            "recorded": int(sync_result["recorded"]),
            "skipped": int(sync_result["skipped"]),
            "path": str(journal_path),
        },
    )
    write_lifecycle_event(
        "FOREST_ROADMAP_SYNCED",
        {
            "project": safe_project,
            "received": len(payload.items),
            "recorded": int(sync_result["recorded"]),
            "skipped": int(sync_result["skipped"]),
            "path": str(journal_path),
        },
        skill_id="forest.roadmap",
    )

    return {
        "status": "ok",
        "project": safe_project,
        "path": str(journal_path),
        "received": int(sync_result["received"]),
        "recorded": int(sync_result["recorded"]),
        "skipped": int(sync_result["skipped"]),
        "recorded_items": recorded_entries[:20],
        "skipped_items": skipped_items[:20],
        "policy": sync_result["policy"],
    }


@router.get("/projects/{project_name}/roadmap/journal")
async def get_roadmap_journal(
    project_name: str,
    limit: int = Query(default=30, ge=1, le=200),
):
    safe_project = sanitize_project_name(project_name)
    journal = read_roadmap_journal(project_name=safe_project, limit=limit)
    return {
        "status": "ok",
        "project": safe_project,
        **journal,
    }


@router.post("/projects/{project_name}/canopy/export")
async def canopy_export(
    project_name: str,
    view: Literal["focus", "overview"] = Query(default="overview"),
    risk_threshold: float = Query(default=0.8, ge=0.0, le=1.0),
    module_sort: Literal["importance", "progress", "risk"] = Query(default="importance"),
    event_filter: Literal["all", "analysis", "work", "canopy", "question", "bitmap"] = Query(default="all"),
):
    safe_project = sanitize_project_name(project_name)
    session = session_factory()
    try:
        data = build_canopy_data(
            project_name=safe_project,
            session=session,
            view=view,
            risk_threshold=risk_threshold,
            module_sort=module_sort,
            event_filter=event_filter,
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        )
        exported = export_canopy_dashboard(project_name=safe_project, data=data)
        _save_system_message(
            session=session,
            content="주인님, 현황판이 갱신되었습니다.",
            context_tag="forest:canopy",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    append_project_ledger_event(
        project_name=safe_project,
        event_type="CANOPY_EXPORTED",
        target=safe_project,
        summary="canopy dashboard exported",
        payload={"status_summary": data.get("status_summary", {})},
    )
    write_lifecycle_event(
        "FOREST_CANOPY_EXPORTED",
        {
            "project": safe_project,
            "status_summary": data.get("status_summary", {}),
        },
        skill_id="forest.canopy",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "dashboard_path": exported["dashboard_path"],
        "snapshot_path": exported["snapshot_path"],
        "status_summary": data["status_summary"],
        "risk": data["risk"],
        "module_overview": data.get("module_overview", []),
        "roadmap": data.get("roadmap", {}),
        "sone_summary": data.get("sone_summary", {}),
        "filters": data.get("filters", {}),
    }


@router.post("/projects/{project_name}/status/sync")
async def sync_project_status(
    project_name: str,
    view: Literal["focus", "overview"] = Query(default="focus"),
    risk_threshold: float = Query(default=0.8, ge=0.0, le=1.0),
    module_sort: Literal["importance", "progress", "risk"] = Query(default="importance"),
    event_filter: Literal["all", "analysis", "work", "canopy", "question", "bitmap"] = Query(default="all"),
    export_canopy: bool = Query(default=True),
):
    safe_project = sanitize_project_name(project_name)
    session = session_factory()
    try:
        data = build_canopy_data(
            project_name=safe_project,
            session=session,
            view=view,
            risk_threshold=risk_threshold,
            module_sort=module_sort,
            event_filter=event_filter,
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        )
        synced = sync_progress_snapshot(project_name=safe_project, canopy_data=data)
        if isinstance(synced.get("snapshot"), dict):
            data["progress_sync"] = {"status": "synced", **dict(synced["snapshot"])}
        exported_dashboard_path = ""
        exported_snapshot_path = ""
        if export_canopy:
            exported = export_canopy_dashboard(project_name=safe_project, data=data)
            exported_dashboard_path = str(exported.get("dashboard_path", ""))
            exported_snapshot_path = str(exported.get("snapshot_path", ""))
        _save_system_message(
            session=session,
            content="주인님, 현재 진행상태와 로드맵을 동기화했습니다.",
            context_tag="forest:canopy",
            linked_node="forest:status",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    status_summary = data.get("status_summary") if isinstance(data.get("status_summary"), dict) else {}
    append_project_ledger_event(
        project_name=safe_project,
        event_type="STATUS_SYNCED",
        target=safe_project,
        summary="project progress snapshot synced",
        payload={
            "remaining_work": int(data.get("roadmap", {}).get("remaining_work", 0) or 0),
            "blocked": int(status_summary.get("BLOCKED", 0) or 0),
            "unverified": int(status_summary.get("UNVERIFIED", 0) or 0),
            "export_canopy": bool(export_canopy),
        },
    )
    write_lifecycle_event(
        "FOREST_STATUS_SYNCED",
        {
            "project": safe_project,
            "remaining_work": int(data.get("roadmap", {}).get("remaining_work", 0) or 0),
            "blocked": int(status_summary.get("BLOCKED", 0) or 0),
            "unverified": int(status_summary.get("UNVERIFIED", 0) or 0),
            "snapshot_path": synced.get("snapshot_path", ""),
            "roadmap_path": synced.get("roadmap_path", ""),
            "export_canopy": bool(export_canopy),
        },
        skill_id="forest.status",
    )
    roadmap_live = _record_live_roadmap_entry(
        project_name=safe_project,
        title="[forest] status sync",
        summary=(
            "remaining_work={remaining} blocked={blocked} unverified={unverified}".format(
                remaining=int(data.get("roadmap", {}).get("remaining_work", 0) or 0),
                blocked=int(status_summary.get("BLOCKED", 0) or 0),
                unverified=int(status_summary.get("UNVERIFIED", 0) or 0),
            )
        ),
        category="SYSTEM_CHANGE",
        tags=["forest", "status-sync", "live"],
        note="status/sync",
    )
    return {
        "status": "ok",
        "project": safe_project,
        "progress_snapshot_path": synced.get("snapshot_path", ""),
        "progress_roadmap_path": synced.get("roadmap_path", ""),
        "dashboard_path": exported_dashboard_path,
        "canopy_snapshot_path": exported_snapshot_path,
        "summary": data.get("roadmap", {}),
        "roadmap_live_record": {
            "recorded": int(roadmap_live.get("recorded", 0) or 0),
            "skipped": int(roadmap_live.get("skipped", 0) or 0),
        },
    }


@router.get("/projects/{project_name}/handoff")
async def get_project_handoff(project_name: str):
    safe_project = sanitize_project_name(project_name)
    session = session_factory()
    try:
        data = build_canopy_data(
            project_name=safe_project,
            session=session,
            view="focus",
            focus_mode=bool(getattr(settings, "forest_focus_mode", True)),
            focus_lock_level=str(getattr(settings, "forest_focus_lock_level", "soft")),
            wip_limit=max(1, int(getattr(settings, "forest_wip_limit", 1) or 1)),
        )
    finally:
        session.close()

    focus = data.get("focus") if isinstance(data.get("focus"), dict) else {}
    mission = focus.get("current_mission") if isinstance(focus.get("current_mission"), dict) else {}
    next_action = focus.get("next_action") if isinstance(focus.get("next_action"), dict) else {}

    spec_rows = _build_spec_index(project_name=safe_project, limit=300)
    pending_count = 0
    review_count = 0
    confirmed_count = 0
    needs_review: list[dict[str, Any]] = []
    for row in spec_rows:
        status = _normalize_spec_status(str(row.get("status", "")))
        if status == "pending":
            pending_count += 1
        elif status == "review":
            review_count += 1
        elif status == "confirmed":
            confirmed_count += 1
        if status in {"pending", "review"}:
            needs_review.append(
                {
                    "path": str(row.get("path", "")),
                    "title": str(row.get("title", "")),
                    "status": status,
                    "doc_type": str(row.get("doc_type", "other")),
                    "linked_records": int(row.get("linked_records", 0) or 0),
                    "updated_at": str(row.get("updated_at", "")),
                }
            )
    needs_review.sort(
        key=lambda item: (
            0 if str(item.get("status", "")) == "review" else 1,
            -(int(item.get("linked_records", 0) or 0)),
            str(item.get("title", "")),
        )
    )

    todo_items = _sort_todo_items(_load_todo_items(safe_project))
    todo_count = 0
    doing_count = 0
    done_count = 0
    for row in todo_items:
        status = _normalize_todo_status(str(row.get("status", "")))
        if status == "doing":
            doing_count += 1
        elif status == "done":
            done_count += 1
        else:
            todo_count += 1
    todo_next = [
        row
        for row in todo_items
        if _normalize_todo_status(str(row.get("status", ""))) in {"todo", "doing"}
    ][:8]

    operator_workflow = str((BASE_DIR / "Docs" / "forest_operator_workflow.md").resolve())
    agent_handoff = str((BASE_DIR / "Docs" / "forest_agent_handoff.md").resolve())

    checklist = [
        "1) 루트(소피아) 선택 후 문서 상태(pending/review/confirmed)부터 확인",
        "2) review/pending 문서가 있으면 SonE 검토 실행 후 상태 재분류",
        "3) TODO에서 priority_weight 높은 항목 1개를 doing으로 전환",
        "4) 구현 후 status/sync 실행으로 현황/다음액션 갱신",
    ]

    return {
        "status": "ok",
        "project": safe_project,
        "focus": {
            "current_mission_id": str(focus.get("current_mission_id", "")),
            "current_mission_title": str(mission.get("title", "")),
            "current_mission_status": str(mission.get("status", "")),
            "next_action_text": str(next_action.get("text", "")),
            "next_action_type": str(next_action.get("type", "")),
            "next_action_ref": str(next_action.get("ref", "")),
        },
        "docs": {
            "total": len(spec_rows),
            "pending": pending_count,
            "review": review_count,
            "confirmed": confirmed_count,
            "needs_review": needs_review,
        },
        "todo": {
            "total": len(todo_items),
            "todo": todo_count,
            "doing": doing_count,
            "done": done_count,
            "next": todo_next,
        },
        "checklist": checklist,
        "sources": {
            "operator_workflow": operator_workflow,
            "agent_handoff": agent_handoff,
        },
    }


@router.get("/projects/{project_name}/apple/status-plan")
async def get_apple_status_plan(project_name: str):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    return _build_apple_status_plan(safe_project)


@router.post("/projects/{project_name}/apple/plan/sync")
async def sync_apple_plan(project_name: str, payload: ApplePlanSyncRequest | None = None):
    safe_project = sanitize_project_name(project_name)
    ensure_project_layout(safe_project)
    owner = str((payload.owner if payload else "codex") or "codex").strip().lower() or "codex"
    lane = str((payload.lane if payload else "codex") or "codex").strip().lower() or owner
    force = bool((payload.force if payload else False) or False)

    items = _load_todo_items(safe_project)
    now_iso = _to_iso(_utc_now())
    created = 0
    updated = 0
    touched_ids: list[str] = []

    for template in _apple_plan_templates():
        plan_id = str(template["id"])
        marker = _apple_plan_marker(plan_id)
        row_id = f"todo_apple_{plan_id}"
        existing_idx = next(
            (
                idx
                for idx, row in enumerate(items)
                if str(row.get("id", "")).strip() == row_id
                or marker in str(row.get("detail", ""))
            ),
            -1,
        )
        if existing_idx < 0:
            entry = {
                "id": row_id,
                "title": str(template["title"]),
                "detail": f"{template['detail']} {marker}".strip(),
                "priority_weight": int(template["priority_weight"]),
                "category": "apple",
                "lane": lane,
                "spec_ref": str(BASE_DIR / "Docs" / "apple" / "apple_intelligence_integration_ssot_v0_1.md"),
                "status": "todo",
                "checked": False,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            items.append(entry)
            created += 1
            touched_ids.append(row_id)
            continue

        row = dict(items[existing_idx])
        changed = False
        if force and _normalize_todo_status(str(row.get("status", ""))) == "done":
            row["status"] = "todo"
            row["checked"] = False
            changed = True
        if marker not in str(row.get("detail", "")):
            row["detail"] = f"{str(row.get('detail', '')).strip()} {marker}".strip()
            changed = True
        if str(row.get("category", "")).strip().lower() != "apple":
            row["category"] = "apple"
            changed = True
        if int(row.get("priority_weight", 0) or 0) != int(template["priority_weight"]):
            row["priority_weight"] = int(template["priority_weight"])
            changed = True
        if changed:
            row["updated_at"] = now_iso
            items[existing_idx] = row
            updated += 1
            touched_ids.append(str(row.get("id", row_id)))

    items = _sort_todo_items(items)
    _save_todo_items(safe_project, items)

    recorded = 0
    skipped = 0
    if created > 0 or updated > 0:
        sync_result = sync_roadmap_entries(
            project_name=safe_project,
            items=[
                {
                    "title": "Apple Intelligence 구현계획 동기화",
                    "summary": f"apple plan synced: created {created}, updated {updated}",
                    "files": [
                        "Docs/apple/apple_intelligence_integration_ssot_v0_1.md",
                        "Docs/apple/shortcuts_bridge_v0_1.md",
                        "api/chat_router.py",
                        "core/ai/providers/foundation_provider.py",
                    ],
                    "tags": [
                        "apple",
                        "plan_sync",
                        f"owner:{owner}",
                        f"lane:{lane}",
                        "scope:project",
                        "phase:apple",
                        "phase_step:apple.1",
                    ],
                    "category": "FEATURE_ADD",
                    "owner": owner,
                    "lane": lane,
                    "scope": "project",
                    "review_state": "review",
                }
            ],
            force_record=False,
            entry_type="SYNC_CHANGE",
        )
        recorded = int(sync_result.get("recorded", 0) or 0)
        skipped = int(sync_result.get("skipped", 0) or 0)

    append_project_ledger_event(
        project_name=safe_project,
        event_type="APPLE_PLAN_SYNCED",
        target="apple_plan",
        summary=f"apple plan synced created={created} updated={updated}",
        payload={"created": created, "updated": updated, "force": force, "recorded": recorded, "skipped": skipped},
    )
    write_lifecycle_event(
        "FOREST_APPLE_PLAN_SYNCED",
        {
            "project": safe_project,
            "created": created,
            "updated": updated,
            "force": force,
            "recorded": recorded,
            "skipped": skipped,
        },
        skill_id="forest.apple",
    )

    return {
        "status": "ok",
        "project": safe_project,
        "created": created,
        "updated": updated,
        "recorded": recorded,
        "skipped": skipped,
        "touched_ids": touched_ids,
        "apple": _build_apple_status_plan(safe_project),
    }
