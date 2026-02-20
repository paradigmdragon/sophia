from __future__ import annotations

import json
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

from core.forest.layout import ensure_project_layout, get_project_root, write_json
from core.forest.sone_reason_codes import reason_category, reason_description
from core.memory.schema import ChatTimelineMessage, MindItem, MindWorkingLog, QuestionPool, WorkPackage
from core.services.bitmap_summary_service import build_bitmap_summary
from core.services.forest_status_service import load_progress_snapshot
from sqlalchemy import text

MODULE_ORDER = ("chat", "note", "editor", "subtitle", "core", "forest")
MODULE_LABELS = {
    "chat": "채팅",
    "note": "소피아 노트",
    "editor": "에디터",
    "subtitle": "자막 편집",
    "core": "코어",
    "forest": "소피아 숲",
}
STATUS_ORDER = ("READY", "IN_PROGRESS", "DONE", "BLOCKED", "FAILED")
MODULE_SORT_OPTIONS = ("importance", "progress", "risk")
EVENT_FILTER_OPTIONS = ("all", "analysis", "work", "canopy", "question", "bitmap")
CANOPY_VIEW_OPTIONS = ("focus", "overview")
DEFAULT_CANOPY_LIMIT = 50
MAX_CANOPY_LIMIT = 200
QUESTION_ACTIONABLE_STATUSES = {"collecting", "ready_to_ask", "pending", "acknowledged"}
TRACKED_ROADMAP_CATEGORIES = {"SYSTEM_CHANGE", "PROBLEM_FIX", "FEATURE_ADD"}
ROADMAP_CATEGORY_STATUS = {
    "SYSTEM_CHANGE": "IN_PROGRESS",
    "FEATURE_ADD": "READY",
    "PROBLEM_FIX": "BLOCKED",
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]

SYSTEM_INVENTORY_SPECS: list[dict[str, Any]] = [
    {
        "id": "forest_canopy",
        "category": "FOREST CORE",
        "feature": "Canopy 관제/현황판",
        "module": "forest",
        "description": "숲 현황판 데이터 생성과 데스크탑 시각화",
        "files": [
            "core/forest/canopy.py",
            "api/forest_router.py",
            "apps/desktop/src/pages/ReportPage.tsx",
            "apps/desktop/src/pages/report/DetailPanel.tsx",
        ],
    },
    {
        "id": "forest_sync",
        "category": "FOREST CORE",
        "feature": "Roadmap/Status 동기화 루프",
        "module": "forest",
        "description": "status/sync + roadmap/sync + loop 스크립트 기반 동기화",
        "files": [
            "core/services/forest_status_service.py",
            "core/services/forest_roadmap_sync_service.py",
            "scripts/sync_forest_loop.py",
            "api/forest_router.py",
        ],
    },
    {
        "id": "chat_engine",
        "category": "CHAT",
        "feature": "채팅 응답/게이트 파이프라인",
        "module": "chat",
        "description": "chat_router + local_chat_engine + contract/gate",
        "files": [
            "api/chat_router.py",
            "core/chat/local_chat_engine.py",
            "core/chat/chat_contract.py",
            "core/chat/chat_gate.py",
            "apps/desktop/src/pages/ChatPage.tsx",
        ],
    },
    {
        "id": "ai_pipeline",
        "category": "AI",
        "feature": "AI contract/gate 라우팅",
        "module": "core",
        "description": "ai_router + providers + contracts",
        "files": [
            "api/ai_router.py",
            "core/ai/ai_router.py",
            "core/ai/gate.py",
            "core/ai/contracts/ingest_contract.py",
            "core/ai/providers/ollama_provider.py",
        ],
    },
    {
        "id": "work_lifecycle",
        "category": "WORK",
        "feature": "Work package 수명주기",
        "module": "core",
        "description": "work 생성/진행/완료 + focus 정책",
        "files": [
            "api/work_router.py",
            "core/services/focus_policy_service.py",
            "core/memory/schema.py",
        ],
    },
    {
        "id": "note_pipeline",
        "category": "NOTES",
        "feature": "소피아 노트/리플렉션",
        "module": "note",
        "description": "노트 페이지 + 반영 스크립트",
        "files": [
            "apps/desktop/src/pages/SophiaNotePage.tsx",
            "api/sophia_notes.py",
            "scripts/daily_reflect.py",
            "scripts/daily_brief.py",
        ],
    },
    {
        "id": "editor_pipeline",
        "category": "EDITOR",
        "feature": "에디터/명세 분석 연계",
        "module": "editor",
        "description": "에디터 입력과 SonE/Grove 분석 경로",
        "files": [
            "apps/desktop/src/pages/EditorPage.tsx",
            "api/sone_router.py",
            "core/forest/grove.py",
        ],
    },
    {
        "id": "subtitle_pipeline",
        "category": "SUBTITLE",
        "feature": "자막 파이프라인",
        "module": "subtitle",
        "description": "Hearing UI + ASR/refine 파이프라인",
        "files": [
            "apps/desktop/src/pages/HearingPage.tsx",
            "core/app/pipeline.py",
            "core/app/asr/whisper_engine.py",
            "core/app/refine/refiner.py",
        ],
    },
    {
        "id": "bitmap_pipeline",
        "category": "BITMAP",
        "feature": "Bitmap 저장/검증 파이프라인",
        "module": "core",
        "description": "요약/감사/validator + canopy 상태 반영",
        "files": [
            "core/services/bitmap_summary_service.py",
            "core/services/bitmap_audit_service.py",
            "core/engine/bitmap_validator.py",
            "api/mind_router.py",
        ],
    },
    {
        "id": "apple_shortcuts",
        "category": "APPLE",
        "feature": "Shortcuts/Bridge 연계",
        "module": "chat",
        "description": "generation meta + shortcuts 브릿지 문서/경로",
        "files": [
            "docs/apple/shortcuts_bridge_v0_1.md",
            "docs/apple/apple_intelligence_integration_ssot_v0_1.md",
            "core/llm/generation_meta.py",
            "api/chat_router.py",
        ],
    },
]


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _read_recent_events(project_name: str, limit: int = 80) -> list[dict[str, Any]]:
    path = get_project_root(project_name) / "ledger" / "ledger.jsonl"
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
    return rows[-limit:]


def _normalize_roadmap_entry(row: dict[str, Any], *, index: int) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    title = str(row.get("title", "")).strip()
    summary = str(row.get("summary", "")).strip()
    if not title and not summary:
        return None
    category = str(row.get("category", "")).strip().upper() or "SYSTEM_CHANGE"
    if category not in TRACKED_ROADMAP_CATEGORIES:
        return None
    entry_type = str(row.get("type", "")).strip().upper() or "SYNC_CHANGE"
    recorded_at = str(row.get("recorded_at", "")).strip() or str(row.get("timestamp", "")).strip()
    files = [
        str(value).strip()
        for value in (row.get("files") if isinstance(row.get("files"), list) else [])
        if str(value).strip()
    ]
    tags = [
        str(value).strip()
        for value in (row.get("tags") if isinstance(row.get("tags"), list) else [])
        if str(value).strip()
    ]
    spec_refs = [
        str(value).strip()
        for value in (row.get("spec_refs") if isinstance(row.get("spec_refs"), list) else [])
        if str(value).strip()
    ]
    phase = str(row.get("phase", "")).strip()
    phase_step = str(row.get("phase_step", "")).strip()
    phase_title = str(row.get("phase_title", "")).strip()
    owner = str(row.get("owner", "")).strip()
    lane = str(row.get("lane", "")).strip()
    scope = str(row.get("scope", "")).strip().lower()
    review_state = str(row.get("review_state", "")).strip().lower()

    for tag in tags:
        low = tag.lower()
        if not owner and low.startswith("owner:"):
            owner = tag.split(":", 1)[1].strip()
        if not lane and low.startswith("lane:"):
            lane = tag.split(":", 1)[1].strip()
        if not scope and low.startswith("scope:"):
            scope = tag.split(":", 1)[1].strip().lower()
        if not review_state and low.startswith("review_state:"):
            review_state = tag.split(":", 1)[1].strip().lower()
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
    if not lane:
        lane = owner
    if not owner:
        owner = "codex" if str(row.get("type", "")).strip().upper().startswith("SYNC") else "unknown"
    if not lane:
        lane = "unassigned"
    if scope not in {"forest", "project"}:
        file_paths = [
            str(value).strip().lower()
            for value in (row.get("files") if isinstance(row.get("files"), list) else [])
            if str(value).strip()
        ]
        forest_tokens = ("core/forest", "api/forest_router", "apps/desktop/src/pages/report", "/forest/")
        scope = "forest" if any(any(token in path for token in forest_tokens) for path in file_paths) else "project"
    if review_state not in {"draft", "review_requested", "applied"}:
        review_state = "unknown"
    source = "sync"
    if entry_type.startswith("FOCUS"):
        source = "manual"
    elif entry_type.startswith("SYNC"):
        source = "sync"
    else:
        source = "system"
    fallback_id = f"roadmap_{index:06d}"
    return {
        "id": str(row.get("fingerprint", "")).strip() or fallback_id,
        "recorded_at": recorded_at,
        "timestamp": recorded_at,
        "title": title or summary,
        "summary": summary,
        "category": category,
        "type": entry_type,
        "category_reason": str(row.get("category_reason", "")).strip(),
        "source": source,
        "files": files,
        "tags": tags,
        "spec_refs": sorted(set(spec_refs)),
        "phase": phase,
        "phase_step": phase_step,
        "phase_title": phase_title,
        "owner": owner,
        "lane": lane,
        "scope": scope,
        "review_state": review_state,
        "status": ROADMAP_CATEGORY_STATUS.get(category, "DONE"),
    }


def _build_parallel_workboard(*, roadmap_entries: list[dict[str, Any]], max_items_per_lane: int = 8) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    unassigned = 0

    for row in roadmap_entries:
        if not isinstance(row, dict):
            continue
        lane = str(row.get("lane", "")).strip().lower() or str(row.get("owner", "")).strip().lower()
        if not lane:
            lane = "unassigned"
        status = str(row.get("status", "")).strip().upper() or ROADMAP_CATEGORY_STATUS.get(
            str(row.get("category", "")).strip().upper(),
            "DONE",
        )
        if lane == "unassigned":
            unassigned += 1
        bucket = lanes.setdefault(
            lane,
            {
                "owner": lane,
                "label": lane,
                "active": 0,
                "ready": 0,
                "blocked": 0,
                "done": 0,
                "items": [],
            },
        )
        if status == "IN_PROGRESS":
            bucket["active"] += 1
        elif status == "READY":
            bucket["ready"] += 1
        elif status in {"BLOCKED", "FAILED"}:
            bucket["blocked"] += 1
        else:
            bucket["done"] += 1

        item = {
            "id": str(row.get("id", "")).strip(),
            "title": str(row.get("title", "")).strip() or str(row.get("summary", "")).strip(),
            "summary": str(row.get("summary", "")).strip(),
            "status": status,
            "scope": str(row.get("scope", "project")).strip().lower() or "project",
            "phase_step": str(row.get("phase_step", "")).strip(),
            "recorded_at": str(row.get("recorded_at", "")).strip(),
            "review_state": str(row.get("review_state", "unknown")).strip(),
        }
        bucket["items"].append(item)

    lane_list = list(lanes.values())
    for row in lane_list:
        row["items"] = row["items"][:max(1, int(max_items_per_lane))]
    lane_list.sort(
        key=lambda row: (
            -int(row.get("active", 0) or 0),
            -int(row.get("blocked", 0) or 0),
            str(row.get("label", "")),
        )
    )
    return {
        "lanes": lane_list,
        "unassigned_count": int(unassigned),
        "updated_at": _to_iso(datetime.now(UTC)),
    }


def _build_mind_workstream(*, session, recent_limit: int = 120) -> dict[str, Any]:
    learning_rows = session.execute(
        text(
            """
            SELECT event_type, COUNT(*) AS count
            FROM mind_working_logs
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 20
            """
        )
    ).fetchall()
    learning_events: dict[str, int] = {}
    for row in learning_rows:
        event_type = str(row[0] or "").strip()
        if not event_type:
            continue
        learning_events[event_type] = int(row[1] or 0)

    chat_kinds: dict[str, int] = {}
    note_context_messages = 0
    recent_chat_rows = (
        session.query(ChatTimelineMessage)
        .order_by(ChatTimelineMessage.created_at.desc(), ChatTimelineMessage.id.desc())
        .limit(max(1, int(recent_limit)))
        .all()
    )
    for row in recent_chat_rows:
        context = str(row.context_tag or "").strip().lower()
        if context in {"memo", "note", "notes", "roots"}:
            note_context_messages += 1
        meta = row.meta if isinstance(row.meta, dict) else {}
        kind = str(meta.get("kind", "")).strip().upper()
        if kind:
            chat_kinds[kind] = int(chat_kinds.get(kind, 0)) + 1

    top_learning = sorted(learning_events.items(), key=lambda item: item[1], reverse=True)[:8]
    top_chat = sorted(chat_kinds.items(), key=lambda item: item[1], reverse=True)[:8]

    return {
        "learning_events": {key: int(value) for key, value in top_learning},
        "chat_kinds": {key: int(value) for key, value in top_chat},
        "note_context_messages": int(note_context_messages),
        "recent_chat_scanned": int(len(recent_chat_rows)),
        "updated_at": _to_iso(datetime.now(UTC)),
    }


def read_roadmap_journal(*, project_name: str, limit: int = 50) -> dict[str, Any]:
    path = get_project_root(project_name) / "status" / "roadmap_journal.jsonl"
    normalized_limit = max(1, int(limit or 1))
    if not path.exists():
        return {
            "path": str(path),
            "total": 0,
            "entries": [],
            "last_recorded_at": "",
            "category_counts": {key: 0 for key in sorted(TRACKED_ROADMAP_CATEGORIES)},
            "phase_counts": {},
            "current_phase": "",
            "current_phase_step": "",
        }

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for idx, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            normalized = _normalize_roadmap_entry(parsed, index=idx)
            if normalized is not None:
                rows.append(normalized)

    total = len(rows)
    recent_rows = list(reversed(rows[-normalized_limit:]))
    category_counts: dict[str, int] = {key: 0 for key in sorted(TRACKED_ROADMAP_CATEGORIES)}
    phase_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("category", "")).strip().upper()
        if key in category_counts:
            category_counts[key] += 1
        phase_key = str(row.get("phase", "")).strip()
        if phase_key:
            phase_counts[phase_key] = phase_counts.get(phase_key, 0) + 1
    last_recorded_at = ""
    current_phase = ""
    current_phase_step = ""
    for row in recent_rows:
        value = str(row.get("recorded_at", "")).strip()
        if value:
            last_recorded_at = value
        if not current_phase:
            current_phase = str(row.get("phase", "")).strip()
        if not current_phase_step:
            current_phase_step = str(row.get("phase_step", "")).strip()
        break

    return {
        "path": str(path),
        "total": total,
        "entries": recent_rows,
        "last_recorded_at": last_recorded_at,
        "category_counts": category_counts,
        "phase_counts": phase_counts,
        "current_phase": current_phase,
        "current_phase_step": current_phase_step,
    }


def _read_engine_bitmap_events(session, *, limit: int = 80) -> list[dict[str, Any]]:
    bind = session.get_bind()
    if bind is None:
        return []
    try:
        rows = session.execute(
            text(
                """
            SELECT event_id, episode_id, type, payload, at
            FROM events
            WHERE type IN ('BITMAP_INVALID', 'PROPOSE', 'ADOPT', 'REJECT', 'CONFLICT_MARK', 'EPIDORA_MARK')
            ORDER BY at DESC
            LIMIT :limit
            """
            ),
            {"limit": int(limit)},
        ).fetchall()
    except Exception:
        return []

    output: list[dict[str, Any]] = []
    for row in rows:
        payload_raw = row[3]
        payload: dict[str, Any] = {}
        if isinstance(payload_raw, dict):
            payload = payload_raw
        elif isinstance(payload_raw, str):
            try:
                parsed = json.loads(payload_raw)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}

        event_type = str(row[2] or "").upper()
        episode_id = str(row[1] or "").strip()
        candidate_id = str(payload.get("candidate_id", "")).strip()
        target = candidate_id or episode_id or "engine"
        when = row[4]
        level = "info"
        summary = ""

        if event_type == "BITMAP_INVALID":
            stage = str(payload.get("stage", "")).strip().lower() or "propose"
            reason = str(payload.get("reason", "INVALID_BITMAP")).strip().upper() or "INVALID_BITMAP"
            bits_value = payload.get("bits_raw")
            bits_text = str(bits_value)
            if isinstance(bits_value, int):
                bits_text = f"0x{int(bits_value) & 0xFFFF:04X}"
            summary = f"bitmap invalid ({stage}) {reason} {bits_text}"
            level = "warning"
        elif event_type == "PROPOSE":
            count = int(payload.get("count", 0) or 0)
            source = str(payload.get("source", "")).strip() or "unknown"
            summary = f"bitmap propose count={count} source={source}"
            level = "info"
        elif event_type == "ADOPT":
            backbone_id = str(payload.get("backbone_id", "")).strip() or "-"
            summary = f"bitmap adopt candidate={candidate_id or '-'} backbone={backbone_id}"
            level = "info"
        elif event_type == "REJECT":
            reason = str(payload.get("reason", "")).strip()
            summary = f"bitmap reject candidate={candidate_id or '-'}"
            if reason:
                summary = f"{summary} reason={reason}"
            level = "warning"
        elif event_type == "CONFLICT_MARK":
            summary = "bitmap conflict mark"
            level = "warning"
        elif event_type == "EPIDORA_MARK":
            name = str(payload.get("name", "")).strip() or "EPIDORA"
            summary = f"epidora mark {name}"
            level = "warning"
        else:
            summary = f"engine event {event_type}"

        output.append(
            {
                "timestamp": _to_iso(when if isinstance(when, datetime) else None),
                "event_type": event_type,
                "target": target,
                "summary": summary,
                "payload": payload,
                "level": level,
            }
        )
    output.reverse()
    return output


def _build_bitmap_pipeline_status(bitmap_health: dict[str, Any] | None) -> dict[str, Any]:
    metrics = bitmap_health if isinstance(bitmap_health, dict) else {}
    invalid_count = int(metrics.get("invalid_count_7d", 0) or 0)
    conflict_count = int(metrics.get("conflict_mark_count_7d", 0) or 0)
    duplicate_rows = int(metrics.get("duplicate_backbone_rows", 0) or 0)
    pending_count = int(metrics.get("pending_count", 0) or 0)
    candidate_count = int(metrics.get("candidate_count_7d", 0) or 0)
    adoption_rate = float(metrics.get("adoption_rate", 0.0) or 0.0)

    status = "healthy"
    reasons: list[str] = []
    next_action = "bitmap 파이프라인 이상 없음"
    action_type = "bitmap_ok"
    action_ref = "bitmap"

    if invalid_count > 0 or duplicate_rows > 0:
        status = "critical"
        if invalid_count > 0:
            reasons.append(f"INVALID 이벤트 {invalid_count}건")
        if duplicate_rows > 0:
            reasons.append(f"중복 backbone {duplicate_rows}건")
        if invalid_count > 0:
            next_action = f"BITMAP_INVALID {invalid_count}건 원인코드 상위 1개부터 수정"
            action_type = "bitmap_invalid_fix"
            action_ref = "BITMAP_INVALID"
        else:
            next_action = f"중복 backbone {duplicate_rows}건 정리 후 merge/validator 규칙 재검증"
            action_type = "bitmap_duplicate_fix"
            action_ref = "DUPLICATE_BACKBONE"
    elif conflict_count > 0 or pending_count >= 20 or (candidate_count > 0 and adoption_rate < 0.35):
        status = "warning"
        if conflict_count > 0:
            reasons.append(f"CONFLICT_MARK {conflict_count}건")
        if pending_count >= 20:
            reasons.append(f"pending candidate {pending_count}건")
        if candidate_count > 0 and adoption_rate < 0.35:
            reasons.append(f"adoption_rate {adoption_rate:.2f}")
        if pending_count >= 20:
            next_action = f"pending candidate {pending_count}건 중 우선순위 상위 3건 adopt/reject 결정"
            action_type = "bitmap_pending_triage"
            action_ref = "PENDING_CANDIDATE"
        elif candidate_count > 0 and adoption_rate < 0.35:
            next_action = f"adoption_rate {adoption_rate:.2f} 개선: candidate 판정 기준(채택/반려) 1차 정리"
            action_type = "bitmap_adoption_tune"
            action_ref = "ADOPTION_RATE"
        else:
            next_action = f"CONFLICT_MARK {conflict_count}건 연결관계 확인 후 충돌 원인 정리"
            action_type = "bitmap_conflict_triage"
            action_ref = "CONFLICT_MARK"

    return {
        "status": status,
        "window_days": int(metrics.get("window_days", 7) or 7),
        "reasons": reasons,
        "next_action": next_action,
        "action_type": action_type,
        "action_ref": action_ref,
        "metrics": {
            "candidate_count_7d": candidate_count,
            "pending_count": pending_count,
            "invalid_count_7d": invalid_count,
            "conflict_mark_count_7d": conflict_count,
            "duplicate_backbone_rows": duplicate_rows,
            "adoption_rate": adoption_rate,
        },
    }


def _read_json(path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _module_from_node(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "forest"
    if any(token in raw for token in ("bitmap", "validator", "engine", "gate", "core")):
        return "core"
    if any(token in raw for token in ("chat", "dialog", "conversation")):
        return "chat"
    if any(token in raw for token in ("note", "memo")):
        return "note"
    if any(token in raw for token in ("editor", "doc", "spec", "markdown", ".md")):
        return "editor"
    if any(token in raw for token in ("subtitle", "caption", "hearing", "srt")):
        return "subtitle"
    return "forest"


def _module_from_context(context_tag: str | None, linked_node: str | None) -> str:
    tag = str(context_tag or "").strip().lower()
    linked = str(linked_node or "").strip().lower()
    if any(token in tag for token in ("core", "bitmap", "engine")) or any(
        token in linked for token in ("core", "bitmap", "engine")
    ):
        return "core"
    if tag.startswith("forest:"):
        return "forest"
    if tag in {"work", "question-queue", "roots", "system", "forest"}:
        return "forest"
    if tag in {"chat", "general", "question"}:
        return "chat"
    if tag in {"memo", "note", "notes"}:
        return "note"
    if tag in {"editor", "docs"}:
        return "editor"
    if tag in {"hearing", "subtitle", "captions"}:
        return "subtitle"
    return _module_from_node(linked_node)


def _work_status(row: WorkPackage) -> str:
    status = str(row.status or "").strip().upper()
    if status in {"READY", "IN_PROGRESS", "DONE", "BLOCKED", "FAILED"}:
        return status

    payload = row.payload if isinstance(row.payload, dict) else {}
    report = payload.get("last_report") if isinstance(payload, dict) else None
    report_status = ""
    if isinstance(report, dict):
        report_status = str(report.get("status", "")).strip().upper()
    if report_status in {"DONE", "BLOCKED", "FAILED"}:
        return report_status
    return "READY"


def _project_name_for_work(row: WorkPackage) -> str:
    payload = row.payload if isinstance(row.payload, dict) else {}
    project = payload.get("project")
    if isinstance(project, str) and project.strip():
        return project.strip().lower()
    return "sophia"


def _work_priority_score(status: str, linked_risk: float) -> int:
    base = {
        "FAILED": 95,
        "BLOCKED": 90,
        "IN_PROGRESS": 75,
        "READY": 60,
        "DONE": 20,
    }.get(status, 50)
    return int(min(100, base + int(max(0.0, linked_risk) * 25)))


def _build_sone_summary(project_name: str) -> dict[str, Any]:
    root = get_project_root(project_name)
    analysis_dir = root / "analysis"

    last_delta = _read_json(analysis_dir / "last_delta.sone.json")
    dependency_graph = _read_json(analysis_dir / "dependency_graph.json")
    risk_snapshot = _read_json(analysis_dir / "risk_snapshot.json")

    slots = last_delta.get("slots") if isinstance(last_delta.get("slots"), list) else []
    missing_slots: list[dict[str, Any]] = []
    impacts: list[str] = []
    impact_seen: set[str] = set()

    for slot in slots:
        if not isinstance(slot, dict):
            continue
        slot_status = str(slot.get("status", "")).strip()
        if slot_status.startswith("missing"):
            reason_codes = slot.get("reason_codes") if isinstance(slot.get("reason_codes"), list) else []
            reason_code = str(reason_codes[0]).strip().upper() if reason_codes else ""
            missing_slots.append(
                {
                    "target": str(slot.get("target", "")).strip(),
                    "status": slot_status,
                    "evidence": str(slot.get("evidence", "")).strip(),
                    "reason_code": reason_code,
                    "reason_description": reason_description(reason_code) if reason_code else "",
                }
            )
        for impact in slot.get("impact", []) if isinstance(slot.get("impact"), list) else []:
            value = str(impact).strip()
            if not value or value in impact_seen:
                continue
            impact_seen.add(value)
            impacts.append(value)

    clusters = risk_snapshot.get("clusters") if isinstance(risk_snapshot.get("clusters"), list) else []
    max_risk = 0.0
    risk_reasons: list[dict[str, Any]] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        score = float(cluster.get("risk_score", 0.0) or 0.0)
        max_risk = max(max_risk, score)
        risk_reasons.append(
            {
                "cluster_id": str(cluster.get("cluster_id", "")).strip(),
                "description": str(cluster.get("description", "")).strip(),
                "risk_score": score,
                "reason_code": str(cluster.get("reason_code", "")).strip().upper(),
                "reason_description": str(cluster.get("reason_description", "")).strip()
                or reason_description(str(cluster.get("reason_code", "")).strip().upper()),
                "category": str(cluster.get("category", "")).strip()
                or reason_category(str(cluster.get("reason_code", "")).strip().upper()),
                "evidence": str(cluster.get("evidence", "")).strip(),
            }
        )

    graph_nodes = dependency_graph.get("nodes") if isinstance(dependency_graph.get("nodes"), list) else []
    graph_edges = dependency_graph.get("edges") if isinstance(dependency_graph.get("edges"), list) else []
    risk_reasons.sort(key=lambda row: float(row.get("risk_score", 0.0) or 0.0), reverse=True)
    generated_at = str(last_delta.get("generated_at", "")).strip()
    generated_parsed = _parse_iso_datetime(generated_at)
    freshness_minutes = (
        max(0, int((datetime.now(UTC) - generated_parsed).total_seconds() // 60))
        if generated_parsed is not None
        else None
    )
    source_doc = str(last_delta.get("source_doc", "")).strip()
    if not source_doc:
        validation_state = "missing_input"
        validation_next = "명세 업로드 후 Grove 분석 실행"
    elif len(missing_slots) > 0:
        validation_state = "needs_review"
        validation_next = f"누락 슬롯 {len(missing_slots)}건 보완 후 Grove 분석 재실행"
    else:
        validation_state = "ready"
        validation_next = "SonE 분석 결과 유지"

    return {
        "source_doc": source_doc,
        "generated_at": generated_at,
        "validation_stage": "heuristic_v0_1",
        "validation_state": validation_state,
        "validation_next_action": validation_next,
        "freshness_minutes": freshness_minutes,
        "reason_catalog_version": "sone_reason_v0_1",
        "missing_slots": missing_slots,
        "missing_slot_count": len(missing_slots),
        "impact_targets": impacts,
        "impact_count": len(impacts),
        "risk_cluster_count": len(clusters),
        "max_risk_score": max_risk,
        "risk_reasons": risk_reasons[:8],
        "dependency": {
            "node_count": len(graph_nodes),
            "edge_count": len(graph_edges),
        },
    }


def _build_system_inventory(
    *,
    module_overview: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    module_risk: dict[str, float] = {}
    module_progress: dict[str, int] = {}
    module_question_pressure: dict[str, int] = {}
    for row in module_overview:
        module_id = str(row.get("module", "")).strip().lower()
        if not module_id:
            continue
        module_risk[module_id] = float(row.get("max_risk_score", 0.0) or 0.0)
        module_progress[module_id] = int(row.get("progress_pct", 0) or 0)
        module_question_pressure[module_id] = int(row.get("pending_questions", 0) or 0)

    high_risk_count = len([row for row in high_risk_clusters if isinstance(row, dict)])
    rows: list[dict[str, Any]] = []
    high_risk_module_pressure: dict[str, int] = {}
    for cluster in [item for item in high_risk_clusters if isinstance(item, dict)]:
        linked_nodes = cluster.get("linked_nodes") if isinstance(cluster.get("linked_nodes"), list) else []
        module_candidates = {_module_from_node(str(node)) for node in linked_nodes if str(node).strip()}
        if not module_candidates:
            module_candidates = {"forest"}
        for module_id in module_candidates:
            high_risk_module_pressure[module_id] = int(high_risk_module_pressure.get(module_id, 0)) + 1

    for spec in SYSTEM_INVENTORY_SPECS:
        files = [str(path).strip() for path in spec.get("files", []) if str(path).strip()]
        existing_files: list[str] = []
        missing_files: list[str] = []
        latest_mtime = 0.0

        for rel in files:
            target = PROJECT_ROOT / rel
            if target.exists():
                existing_files.append(rel)
                try:
                    latest_mtime = max(latest_mtime, target.stat().st_mtime)
                except OSError:
                    pass
            else:
                missing_files.append(rel)

        total = len(files)
        implemented = len(existing_files)
        file_progress = int(round((implemented / total) * 100.0)) if total > 0 else 0
        module_id = str(spec.get("module", "forest")).strip().lower() or "forest"
        module_progress_pct = int(module_progress.get(module_id, 0))
        progress_pct = int(round((file_progress * 0.6) + (module_progress_pct * 0.4)))

        risk_score = float(module_risk.get(module_id, 0.0))
        question_pressure = int(module_question_pressure.get(module_id, 0) or 0)
        question_pressure += int(high_risk_module_pressure.get(module_id, 0) or 0)
        # 전역 고위험 질문이 존재하면 forest/chat 계열의 실제 운영 리스크를 보정한다.
        if high_risk_count > 0 and module_id in {"forest", "chat"}:
            risk_score = max(risk_score, 0.8)
            question_pressure = max(question_pressure, 1)

        # 파일 유무만으로 DONE 처리하지 않고, 실제 진행/리스크/질문 압력을 함께 반영한다.
        if implemented == 0:
            status = "READY"
        elif risk_score >= 0.9 or question_pressure >= 3:
            status = "BLOCKED"
        elif missing_files or module_progress_pct < 85 or question_pressure > 0 or risk_score >= 0.8:
            status = "IN_PROGRESS"
        else:
            status = "DONE"

        progress_cap = 100
        if status == "READY":
            progress_cap = min(progress_cap, 39)
        elif status == "IN_PROGRESS":
            progress_cap = min(progress_cap, 89)
        elif status == "BLOCKED":
            progress_cap = min(progress_cap, 69)
        if risk_score >= 0.8:
            progress_cap = min(progress_cap, 84)
        if question_pressure > 0:
            progress_cap = min(progress_cap, 89)
        if missing_files:
            progress_cap = min(progress_cap, 94)
        progress_pct = min(max(0, progress_pct), progress_cap)
        if status == "DONE":
            progress_pct = max(progress_pct, 90)
        elif status in {"IN_PROGRESS", "BLOCKED"}:
            progress_pct = min(progress_pct, 89)

        updated_at = ""
        if latest_mtime > 0:
            updated_at = _to_iso(datetime.fromtimestamp(latest_mtime, tz=UTC))

        rows.append(
            {
                "id": str(spec.get("id", "")).strip(),
                "category": str(spec.get("category", "")).strip(),
                "feature": str(spec.get("feature", "")).strip(),
                "module": module_id,
                "status": status,
                "progress_pct": max(0, min(100, progress_pct)),
                "risk_score": max(0.0, min(1.0, risk_score)),
                "question_pressure": question_pressure,
                "updated_at": updated_at,
                "description": str(spec.get("description", "")).strip(),
                "files": files,
                "existing_files": existing_files,
                "missing_files": missing_files,
            }
        )

    rows.sort(
        key=lambda row: (
            -1 if str(row.get("status", "")).upper() in {"BLOCKED", "FAILED"} else 0,
            -float(row.get("risk_score", 0.0) or 0.0),
            int(row.get("progress_pct", 0) or 0),
            str(row.get("feature", "")),
        )
    )
    return rows


def _serialize_work_item(row: WorkPackage, linked_risk: float) -> dict[str, Any]:
    status = _work_status(row)
    module_id = _module_from_context(row.context_tag, row.linked_node)
    payload = row.payload if isinstance(row.payload, dict) else {}
    work_packet = payload.get("work_packet") if isinstance(payload.get("work_packet"), dict) else {}

    return {
        "id": row.id,
        "title": row.title,
        "status": status,
        "module": module_id,
        "module_label": MODULE_LABELS.get(module_id, module_id),
        "kind": str(work_packet.get("kind", "")).strip() or "WORK",
        "context_tag": row.context_tag,
        "linked_node": row.linked_node,
        "linked_risk": float(linked_risk),
        "priority_score": _work_priority_score(status, linked_risk),
        "acceptance_criteria": [
            str(item).strip()
            for item in work_packet.get("acceptance_criteria", [])
            if isinstance(item, str) and str(item).strip()
        ][:5],
        "project": _project_name_for_work(row),
        "created_at": _to_iso(row.created_at),
        "updated_at": _to_iso(row.updated_at),
        "completed_at": _to_iso(row.completed_at),
    }


def _build_module_overview(
    *,
    work_items: list[dict[str, Any]],
    question_queue: list[dict[str, Any]],
    risk_threshold: float = 0.8,
    bitmap_health: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    modules: dict[str, dict[str, Any]] = {
        module_id: {
            "module": module_id,
            "label": MODULE_LABELS[module_id],
            "work_total": 0,
            "ready": 0,
            "in_progress": 0,
            "done": 0,
            "blocked": 0,
            "failed": 0,
            "dev_progress_pct": 0,
            "pending_questions": 0,
            "max_risk_score": 0.0,
            "last_updated_at": "",
        }
        for module_id in MODULE_ORDER
    }

    for item in work_items:
        module_id = str(item.get("module", "forest"))
        if module_id not in modules:
            module_id = "forest"
        row = modules[module_id]
        row["work_total"] += 1
        status = str(item.get("status", "READY"))
        if status == "READY":
            row["ready"] += 1
        elif status == "IN_PROGRESS":
            row["in_progress"] += 1
        elif status == "DONE":
            row["done"] += 1
        elif status == "BLOCKED":
            row["blocked"] += 1
        elif status == "FAILED":
            row["failed"] += 1
        updated_at = str(item.get("updated_at", ""))
        if updated_at and updated_at > str(row.get("last_updated_at", "")):
            row["last_updated_at"] = updated_at

    for question in question_queue:
        question_status = _question_status(str(question.get("status", "")))
        if not _is_question_actionable(question_status):
            continue
        risk = float(question.get("risk_score", 0.0) or 0.0)
        linked_nodes = question.get("linked_nodes") if isinstance(question.get("linked_nodes"), list) else []
        module_candidates = {_module_from_node(str(node)) for node in linked_nodes if str(node).strip()}
        if not module_candidates:
            module_candidates = {"forest"}
        for module_id in module_candidates:
            if module_id not in modules:
                module_id = "forest"
            modules[module_id]["pending_questions"] += 1
            modules[module_id]["max_risk_score"] = max(float(modules[module_id]["max_risk_score"]), risk)

    output: list[dict[str, Any]] = []
    bitmap = bitmap_health if isinstance(bitmap_health, dict) else {}
    bitmap_pressure = min(
        30,
        int(bitmap.get("invalid_count_7d", 0) or 0) * 8
        + int(bitmap.get("conflict_mark_count_7d", 0) or 0) * 10
        + int(bitmap.get("duplicate_combined_groups", 0) or 0) * 6,
    )
    for module_id in MODULE_ORDER:
        row = modules[module_id]
        total = int(row["work_total"])
        done = int(row["done"])
        pending_questions = int(row["pending_questions"])
        dev_progress = int(round((done / total) * 100.0)) if total > 0 else 0
        unresolved_units = total + pending_questions
        progress = int(round((done / unresolved_units) * 100.0)) if unresolved_units > 0 else 0
        risk_score = float(row["max_risk_score"])

        # 진행률은 "완료 작업 수"뿐 아니라 미해결 질문/고위험 신호를 반영한다.
        # 질문/리스크가 남아 있으면 100% 완료로 보이지 않도록 캡을 적용한다.
        progress_cap = 100
        if int(row["failed"]) > 0:
            progress_cap = min(progress_cap, 59)
        if int(row["blocked"]) > 0:
            progress_cap = min(progress_cap, 79)
        if pending_questions > 0:
            progress_cap = min(progress_cap, 89)
        if risk_score >= float(risk_threshold or 0.0):
            progress_cap = min(progress_cap, 94)
        progress = min(progress, progress_cap)

        base_importance = min(
            100,
            int(
                row["blocked"] * 20
                + row["failed"] * 24
                + row["pending_questions"] * 14
                + int(risk_score * 22)
                + max(0, 40 - progress // 2)
            ),
        )
        pressure = bitmap_pressure if module_id == "forest" else 0
        importance = min(100, base_importance + pressure)
        row["dev_progress_pct"] = dev_progress
        row["progress_pct"] = progress
        row["bitmap_pressure"] = pressure
        row["importance"] = importance
        output.append(row)

    return output


def _sort_module_overview(rows: list[dict[str, Any]], *, sort_by: str) -> list[dict[str, Any]]:
    key = str(sort_by or "importance").strip().lower()
    if key not in MODULE_SORT_OPTIONS:
        key = "importance"

    if key == "progress":
        return sorted(
            rows,
            key=lambda row: (-int(row.get("progress_pct", 0) or 0), -int(row.get("importance", 0) or 0), str(row.get("module", ""))),
        )
    if key == "risk":
        return sorted(
            rows,
            key=lambda row: (
                -float(row.get("max_risk_score", 0.0) or 0.0),
                -int(row.get("pending_questions", 0) or 0),
                -int(row.get("importance", 0) or 0),
                str(row.get("module", "")),
            ),
        )
    return sorted(
        rows,
        key=lambda row: (-int(row.get("importance", 0) or 0), -float(row.get("max_risk_score", 0.0) or 0.0), str(row.get("module", ""))),
    )


def _filter_recent_events(rows: list[dict[str, Any]], *, event_filter: str) -> list[dict[str, Any]]:
    mode = str(event_filter or "all").strip().lower()
    if mode not in EVENT_FILTER_OPTIONS or mode == "all":
        return rows

    def keep(event_type: str) -> bool:
        value = event_type.upper()
        if mode == "analysis":
            return "ANALYSIS" in value or "GROVE" in value
        if mode == "work":
            return "WORK" in value or value in {"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID", "CONFLICT_MARK"}
        if mode == "canopy":
            return "CANOPY" in value
        if mode == "question":
            return "QUESTION" in value
        if mode == "bitmap":
            return value in {"PROPOSE", "ADOPT", "REJECT", "BITMAP_INVALID", "CONFLICT_MARK", "EPIDORA_MARK"}
        return True

    return [row for row in rows if keep(str(row.get("event_type", "")))]


def _normalize_limit_offset(*, limit: int, offset: int) -> tuple[int, int]:
    safe_limit = max(1, min(MAX_CANOPY_LIMIT, int(limit)))
    safe_offset = max(0, int(offset))
    return safe_limit, safe_offset


def _paginate_rows(rows: list[dict[str, Any]], *, limit: int, offset: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total = len(rows)
    start = min(offset, total)
    end = min(start + limit, total)
    page = rows[start:end]
    return page, {
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": len(page),
        "has_more": end < total,
    }


def _question_modules(row: dict[str, Any]) -> set[str]:
    linked_nodes = row.get("linked_nodes") if isinstance(row.get("linked_nodes"), list) else []
    modules = {_module_from_node(str(node)) for node in linked_nodes if str(node).strip()}
    return modules or {"forest"}


def _question_status(value: str | None) -> str:
    status = str(value or "").strip().lower()
    if not status:
        return "collecting"
    return status


def _is_question_actionable(status: str | None) -> bool:
    return _question_status(status) in QUESTION_ACTIONABLE_STATUSES


def _question_node_status(*, status: str | None, risk_score: float, risk_threshold: float) -> str:
    normalized = _question_status(status)
    if normalized == "resolved":
        return "RESOLVED"
    if normalized == "acknowledged":
        return "ACKNOWLEDGED"
    if _is_question_actionable(normalized):
        return "UNVERIFIED" if float(risk_score or 0.0) >= float(risk_threshold or 0.0) else "READY"
    return "READY"


def _roadmap_eta_hint(*, works: list[WorkPackage]) -> dict[str, Any]:
    now = datetime.now(UTC)
    remaining = 0
    in_progress = 0
    blocked = 0
    done_last_7d = 0

    for row in works:
        status = _work_status(row)
        if status != "DONE":
            remaining += 1
        if status == "IN_PROGRESS":
            in_progress += 1
        if status == "BLOCKED":
            blocked += 1
        if status == "DONE":
            done_at = row.completed_at or row.updated_at
            if isinstance(done_at, datetime):
                done_utc = done_at if done_at.tzinfo is not None else done_at.replace(tzinfo=UTC)
                done_utc = done_utc.astimezone(UTC)
                if (now - done_utc).total_seconds() <= 7 * 86400:
                    done_last_7d += 1

    if remaining == 0:
        hint = "남은 작업이 없습니다."
        eta_days = 0
    elif done_last_7d > 0:
        velocity_per_day = done_last_7d / 7.0
        eta_days = max(1, int(ceil(remaining / velocity_per_day)))
        hint = f"최근 7일 완료 {done_last_7d}건 기준, 약 {eta_days}일 예상"
    elif in_progress == 0:
        eta_days = None
        hint = "진행 중 작업이 없어 ETA 계산 불가. READY 항목 1건 착수 필요"
    else:
        eta_days = None
        hint = "최근 7일 완료 이력이 없어 ETA 계산 불가. 진행 중 작업 병목 해소 필요"

    if blocked > 0:
        hint = f"{hint} (BLOCKED {blocked}건)"

    return {
        "hint": hint,
        "remaining_work": remaining,
        "done_last_7d": done_last_7d,
        "in_progress": in_progress,
        "blocked": blocked,
        "eta_days": eta_days,
    }


def _build_virtual_plan_items(
    *,
    pending_work: list[dict[str, Any]],
    in_progress_work: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
    progress_sync: dict[str, Any],
    sone_summary: dict[str, Any],
    roadmap_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    # 실제 대기/진행 항목이 있는 경우에는 가상 계획을 만들지 않는다.
    if pending_work or in_progress_work:
        return []

    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    now_iso = _to_iso(datetime.now(UTC))

    # 고위험 질문만 남아 작업 계획이 비어 보이는 경우, 질문 정리용 가상 계획을 노출한다.
    for idx, cluster in enumerate(high_risk_clusters[:3]):
        if not isinstance(cluster, dict):
            continue
        cluster_id = str(cluster.get("cluster_id", "")).strip()
        if not cluster_id:
            continue
        title = f"질문 클러스터 정리: {cluster_id}"
        if title in seen_titles:
            continue
        seen_titles.add(title)
        risk_value = float(cluster.get("risk_score", 0.0) or 0.0)
        rows.append(
            {
                "id": f"virtual_plan:risk:{idx}:{cluster_id}",
                "title": title,
                "label": title,
                "status": "READY",
                "module": "forest",
                "module_label": MODULE_LABELS["forest"],
                "kind": "PLAN",
                "context_tag": "question-queue",
                "linked_node": "forest:question",
                "linked_risk": risk_value,
                "priority_score": 75,
                "acceptance_criteria": [f"risk {risk_value:.2f} 질문 해소 후 후속 작업 연결"],
                "created_at": now_iso,
                "updated_at": now_iso,
                "completed_at": "",
                "virtual": True,
            }
        )

    if rows:
        return rows

    journal_rows = [row for row in (roadmap_entries or []) if isinstance(row, dict)]
    for idx, row in enumerate(journal_rows):
        category = str(row.get("category", "")).strip().upper()
        title = str(row.get("title", "")).strip()
        summary = str(row.get("summary", "")).strip()
        if category not in TRACKED_ROADMAP_CATEGORIES:
            continue
        lowered = title.lower()
        if any(token in lowered for token in ("status sync", "동기화", "canopy exported", "roots export")):
            continue
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        priority = "P1"
        if category == "PROBLEM_FIX":
            priority = "P0"
        elif category == "FEATURE_ADD":
            priority = "P1"
        else:
            priority = "P2"
        reason = summary or f"{category} 항목 실행 계획 수립"
        rows.append(
            {
                "id": f"virtual_plan:roadmap:{idx}:{title[:20]}",
                "title": title,
                "label": title,
                "status": "READY",
                "module": "forest",
                "module_label": MODULE_LABELS["forest"],
                "kind": "PLAN",
                "context_tag": "forest:roadmap",
                "linked_node": "forest:roadmap",
                "linked_risk": 0.0,
                "priority_score": 75 if priority == "P0" else 55 if priority == "P1" else 35,
                "acceptance_criteria": [reason],
                "created_at": now_iso,
                "updated_at": now_iso,
                "completed_at": "",
                "virtual": True,
            }
        )
        if len(rows) >= 3:
            break

    if rows:
        return rows

    next_actions = (
        progress_sync.get("next_actions")
        if isinstance(progress_sync, dict) and isinstance(progress_sync.get("next_actions"), list)
        else []
    )
    for idx, action in enumerate(next_actions):
        if not isinstance(action, dict):
            continue
        title = str(action.get("title", "")).strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        reason = str(action.get("reason", "")).strip()
        rows.append(
            {
                "id": f"virtual_plan:{idx}:{title[:20]}",
                "title": title,
                "label": title,
                "status": "READY",
                "module": "forest",
                "module_label": MODULE_LABELS["forest"],
                "kind": "PLAN",
                "context_tag": "forest:canopy",
                "linked_node": "forest:focus",
                "linked_risk": 0.0,
                "priority_score": 40,
                "acceptance_criteria": [reason] if reason else [],
                "created_at": now_iso,
                "updated_at": now_iso,
                "completed_at": "",
                "virtual": True,
            }
        )
        if len(rows) >= 3:
            break

    if rows:
        return rows

    missing_slots = int(sone_summary.get("missing_slot_count", 0) or 0)
    if missing_slots > 0:
        return [
            {
                "id": "virtual_plan:sone-missing-slots",
                "title": f"SonE missing slot {missing_slots}건 정리",
                "label": f"SonE missing slot {missing_slots}건 정리",
                "status": "READY",
                "module": "forest",
                "module_label": MODULE_LABELS["forest"],
                "kind": "PLAN",
                "context_tag": "forest:grove",
                "linked_node": "forest:analysis",
                "linked_risk": 0.0,
                "priority_score": 45,
                "acceptance_criteria": ["누락 슬롯 보완 후 Grove 분석 재실행"],
                "created_at": now_iso,
                "updated_at": now_iso,
                "completed_at": "",
                "virtual": True,
            }
        ]

    return [
        {
            "id": "virtual_plan:upload-and-analyze",
            "title": "신규 명세 업로드 후 Grove 분석 실행",
            "label": "신규 명세 업로드 후 Grove 분석 실행",
            "status": "READY",
            "module": "forest",
            "module_label": MODULE_LABELS["forest"],
            "kind": "PLAN",
            "context_tag": "forest:grove",
            "linked_node": "forest:analysis",
            "linked_risk": 0.0,
            "priority_score": 35,
            "acceptance_criteria": ["spec/md 업로드", "Grove 분석 결과 생성"],
            "created_at": now_iso,
            "updated_at": now_iso,
            "completed_at": "",
            "virtual": True,
        }
    ]


def _apply_virtual_plan_to_module_overview(
    *,
    module_overview: list[dict[str, Any]],
    virtual_ready_count: int,
    risk_threshold: float,
) -> list[dict[str, Any]]:
    if virtual_ready_count <= 0:
        return module_overview

    output: list[dict[str, Any]] = []
    for row in module_overview:
        if str(row.get("module", "")) != "forest":
            output.append(row)
            continue

        updated = dict(row)
        updated["virtual_ready"] = int(virtual_ready_count)
        updated["ready"] = int(updated.get("ready", 0) or 0) + int(virtual_ready_count)
        updated["work_total"] = int(updated.get("work_total", 0) or 0) + int(virtual_ready_count)

        total = int(updated["work_total"])
        done = int(updated.get("done", 0) or 0)
        pending_questions = int(updated.get("pending_questions", 0) or 0)
        dev_progress = int(round((done / total) * 100.0)) if total > 0 else 0
        unresolved_units = total + pending_questions
        progress = int(round((done / unresolved_units) * 100.0)) if unresolved_units > 0 else 0

        risk_score = float(updated.get("max_risk_score", 0.0) or 0.0)
        progress_cap = 100
        if int(updated.get("failed", 0) or 0) > 0:
            progress_cap = min(progress_cap, 59)
        if int(updated.get("blocked", 0) or 0) > 0:
            progress_cap = min(progress_cap, 79)
        if pending_questions > 0:
            progress_cap = min(progress_cap, 89)
        if risk_score >= float(risk_threshold or 0.0):
            progress_cap = min(progress_cap, 94)
        updated["dev_progress_pct"] = dev_progress
        updated["progress_pct"] = min(progress, progress_cap)

        base_importance = min(
            100,
            int(
                int(updated.get("blocked", 0) or 0) * 20
                + int(updated.get("failed", 0) or 0) * 24
                + pending_questions * 14
                + int(risk_score * 22)
                + max(0, 40 - int(updated["progress_pct"]) // 2)
            ),
        )
        pressure = int(updated.get("bitmap_pressure", 0) or 0)
        updated["importance"] = min(100, base_importance + pressure)
        output.append(updated)
    return output


def _build_connection_graph(
    *,
    module_overview: list[dict[str, Any]],
    work_items: list[dict[str, Any]],
    question_queue: list[dict[str, Any]],
    risk_threshold: float,
) -> dict[str, Any]:
    module_nodes = [
        {
            "id": f"module:{row['module']}",
            "type": "module",
            "label": f"{row['label']}\\n{row['progress_pct']}%",
            "status": "MODULE",
        }
        for row in module_overview
    ]

    sorted_work = sorted(
        work_items,
        key=lambda item: (
            STATUS_ORDER.index(str(item.get("status", "READY"))) if str(item.get("status", "READY")) in STATUS_ORDER else 99,
            -int(item.get("priority_score", 0) or 0),
            str(item.get("updated_at", "")),
        ),
    )
    work_nodes = []
    for item in sorted_work[:24]:
        work_nodes.append(
            {
                "id": f"work:{item['id']}",
                "type": "work",
                "label": f"{item['title']}\\n[{item['status']}]",
                "status": str(item["status"]),
                "module": item["module"],
                "linked_node": item.get("linked_node") or "",
            }
        )

    question_nodes = []
    for row in sorted(question_queue, key=lambda q: (-float(q.get("risk_score", 0.0) or 0.0), -int(q.get("hit_count", 0) or 0)))[:16]:
        risk_score = float(row.get("risk_score", 0.0) or 0.0)
        question_nodes.append(
            {
                "id": f"question:{row['cluster_id']}",
                "type": "question",
                "label": f"{row['cluster_id']}\\n[risk {risk_score:.2f}]",
                "status": _question_node_status(
                    status=str(row.get("status", "")),
                    risk_score=risk_score,
                    risk_threshold=risk_threshold,
                ),
                "linked_nodes": row.get("linked_nodes", []),
            }
        )

    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()

    for node in work_nodes:
        edge = (f"module:{node['module']}", node["id"])
        if edge not in seen_edges:
            seen_edges.add(edge)
            edges.append({"from": edge[0], "to": edge[1]})

    for work in work_nodes:
        linked_node = str(work.get("linked_node", "")).strip().lower()
        linked = False
        for question in question_nodes:
            linked_nodes = [str(value).strip().lower() for value in question.get("linked_nodes", []) if str(value).strip()]
            if linked_node and linked_node in linked_nodes:
                edge = (work["id"], question["id"])
                if edge not in seen_edges:
                    seen_edges.add(edge)
                    edges.append({"from": edge[0], "to": edge[1]})
                linked = True
        if not linked and question_nodes:
            # Keep graph connected with a lightweight module->question fallback.
            first = question_nodes[0]
            edge = (f"module:{work['module']}", first["id"])
            if edge not in seen_edges:
                seen_edges.add(edge)
                edges.append({"from": edge[0], "to": edge[1]})

    return {
        "nodes": [*module_nodes, *work_nodes, *question_nodes],
        "edges": edges,
    }


def _parse_iso_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _select_current_mission(work_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    in_progress = [row for row in work_items if str(row.get("status", "")).upper() == "IN_PROGRESS"]
    if in_progress:
        ordered = sorted(
            in_progress,
            key=lambda row: (
                -int(row.get("priority_score", 0) or 0),
                str(row.get("updated_at", "")),
                str(row.get("id", "")),
            ),
            reverse=False,
        )
        return ordered[0] if ordered else None

    # Focus 화면에서 "현재 미션 없음"으로 비는 상황을 줄이기 위해,
    # 진행중이 없으면 READY/BLOCKED/FAILED 중 최우선 항목을 표시 미션으로 사용한다.
    pending_like = [
        row
        for row in work_items
        if str(row.get("status", "")).upper() in {"READY", "BLOCKED", "FAILED"}
    ]
    if not pending_like:
        return None
    ordered_pending = sorted(
        pending_like,
        key=lambda row: (
            -int(row.get("priority_score", 0) or 0),
            str(row.get("updated_at", "")),
            str(row.get("id", "")),
        ),
        reverse=False,
    )
    return ordered_pending[0] if ordered_pending else None


def _build_next_action(
    *,
    current_mission: dict[str, Any] | None,
    pending_work: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    if current_mission is not None:
        current_status = str(current_mission.get("status", "")).strip().upper()
        mission_id = str(current_mission.get("id", "")).strip()
        title = str(current_mission.get("title", "")).strip() or mission_id
        if current_status in {"BLOCKED", "FAILED"}:
            if high_risk_clusters:
                cluster = high_risk_clusters[0]
                cluster_id = str(cluster.get("cluster_id", "")).strip()
                risk = float(cluster.get("risk_score", 0.0) or 0.0)
                return {
                    "text": f"{title}: 질문 {cluster_id} (risk {risk:.2f})부터 정리",
                    "type": "question_triage",
                    "ref": cluster_id,
                    "work_ref": mission_id,
                }
            action_type = "resolve_blocked" if current_status == "BLOCKED" else "resolve_failed"
            action_reason = "막힘 해소 처리(완료/재계획)" if current_status == "BLOCKED" else "실패 원인 정리 후 재실행"
            return {
                "text": f"{title}: {action_reason}",
                "type": action_type,
                "ref": mission_id,
            }

        criteria = current_mission.get("acceptance_criteria")
        criterion = ""
        if isinstance(criteria, list):
            for item in criteria:
                text = str(item).strip()
                if text:
                    criterion = text
                    break
        if not criterion:
            criterion = "완료 기준을 확인하고 보고 JSON을 제출"
        return {
            "text": f"{title}: {criterion}",
            "type": "work_step",
            "ref": mission_id,
        }

    if pending_work:
        row = pending_work[0]
        title = str(row.get("title", "")).strip() or str(row.get("id", "")).strip()
        status = str(row.get("status", "")).upper()
        reason = "ACK 후 진행 시작"
        if status == "BLOCKED":
            reason = "막힘 원인 1줄과 해소 조건을 먼저 확정"
        elif status == "FAILED":
            reason = "실패 원인 정리 후 재시도 계획 수립"
        return {"text": f"{title}: {reason}", "type": "pending_work", "ref": str(row.get("id", ""))}

    if high_risk_clusters:
        cluster = high_risk_clusters[0]
        cluster_id = str(cluster.get("cluster_id", "")).strip()
        risk = float(cluster.get("risk_score", 0.0) or 0.0)
        return {
            "text": f"질문 클러스터 {cluster_id} (risk {risk:.2f}) 확인",
            "type": "question_triage",
            "ref": cluster_id,
        }

    return {"text": "다음 액션 없음: 신규 명세 업로드 후 Grove 분석 실행", "type": "idle", "ref": ""}


def _build_frozen_ideas(*, session, project_name: str, limit: int = 5) -> dict[str, Any]:
    project_tag = f"project:{project_name}"
    rows = (
        session.query(MindItem)
        .filter(
            MindItem.type == "FOCUS",
            MindItem.status == "parked",
        )
        .order_by(MindItem.updated_at.desc(), MindItem.id.asc())
        .limit(200)
        .all()
    )
    ideas: list[dict[str, str]] = []
    for row in rows:
        tags = [str(tag).strip().lower() for tag in (row.tags or []) if str(tag).strip()]
        if "freeze" not in tags:
            continue
        if project_tag not in tags:
            continue
        idea_tag = ""
        for tag in tags:
            if tag.startswith("idea_tag:"):
                idea_tag = tag.split(":", 1)[1].strip()
                break
        ideas.append(
            {
                "id": str(row.id),
                "title": str(row.title or "").strip(),
                "tag": idea_tag,
                "created_at": _to_iso(row.created_at),
            }
        )
    return {"count": len(ideas), "top": ideas[: max(1, int(limit))]}


def _format_journey_footprint(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "")).strip().upper()
    target = str(event.get("target", "")).strip()
    summary = str(event.get("summary", "")).strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}

    if event_type == "WORK_PACKAGE_CREATED":
        return f"작업 패킷 생성 · {target or '-'}"
    if event_type in {"ANALYSIS", "FOREST_ANALYSIS", "GROVE_ANALYZED"}:
        return f"Grove 분석 완료 · {target or '-'}"
    if event_type in {"STATUS_SYNCED", "FOREST_STATUS_SYNCED"}:
        return "진행상태 동기화 완료"
    if event_type == "CANOPY_EXPORTED":
        return "Canopy 내보내기 완료"
    if event_type == "ROOTS_EXPORT":
        return "Roots 내보내기 완료"
    if event_type == "IDEA_FROZEN":
        return f"아이디어 격리 · {target or '-'}"
    if event_type == "IDEA_PROMOTED":
        return f"아이디어 승격 · {target or '-'}"
    if event_type == "WORK_PACKAGE_REPORTED":
        report_status = str(payload.get("report_status", "")).strip().upper()
        suffix = f" ({report_status})" if report_status else ""
        return f"작업 보고 반영 · {target or '-'}{suffix}"

    base = f"{event_type} · {target}" if target else event_type
    if summary:
        return f"{base} · {summary}"
    return base or "기록 이벤트"


def _compute_streak_days(*, recent_events: list[dict[str, Any]], meaningful: set[str]) -> int | None:
    day_set: set[str] = set()
    for row in recent_events:
        event_type = str(row.get("event_type", "")).strip().upper()
        if event_type not in meaningful:
            continue
        parsed = _parse_iso_datetime(str(row.get("timestamp", "")))
        if parsed is None:
            continue
        day_set.add(parsed.date().isoformat())
    if not day_set:
        return None

    cursor = datetime.now(UTC).date()
    streak = 0
    while cursor.isoformat() in day_set:
        streak += 1
        cursor = type(cursor).fromordinal(cursor.toordinal() - 1)
    return streak


def _build_journey_summary(
    *,
    recent_events: list[dict[str, Any]],
    next_action: dict[str, Any],
) -> tuple[dict[str, Any], int | None]:
    meaningful = {
        "WORK_PACKAGE_CREATED",
        "ANALYSIS",
        "WORK_PACKAGE_REPORTED",
        "WORK_PACKAGE_COMPLETED",
        "GROVE_ANALYZED",
        "FOREST_ANALYSIS",
        "CANOPY_EXPORTED",
        "ROOTS_EXPORT",
        "STATUS_SYNCED",
        "IDEA_FROZEN",
        "IDEA_PROMOTED",
    }
    last = None
    for row in reversed(recent_events):
        event_type = str(row.get("event_type", "")).strip().upper()
        if event_type in meaningful:
            last = row
            break

    if last is None:
        return (
            {
                "last_footprint": "기록된 발자국 없음",
                "next_step": str(next_action.get("text", "")).strip() or "다음 액션 없음",
                "streak_days": None,
            },
            None,
        )

    ts = str(last.get("timestamp", "")).strip()
    footprint = _format_journey_footprint(last)
    parsed = _parse_iso_datetime(ts)
    reentry_minutes: int | None = None
    if parsed is not None:
        reentry_minutes = max(0, int((datetime.now(UTC) - parsed).total_seconds() // 60))
    streak_days = _compute_streak_days(recent_events=recent_events, meaningful=meaningful)

    return (
        {
            "last_footprint": footprint,
            "next_step": str(next_action.get("text", "")).strip() or "다음 액션 없음",
            "streak_days": streak_days,
        },
        reentry_minutes,
    )


def _build_focus_payload(
    *,
    session,
    project_name: str,
    work_items: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
    recent_events: list[dict[str, Any]],
    bitmap_pipeline: dict[str, Any],
    sone_summary: dict[str, Any],
    focus_mode: bool,
    focus_lock_level: str,
    wip_limit: int,
) -> dict[str, Any]:
    in_progress = [row for row in work_items if str(row.get("status", "")).upper() == "IN_PROGRESS"]
    pending = [
        row for row in work_items if str(row.get("status", "")).upper() in {"READY", "BLOCKED", "FAILED"}
    ]
    current_mission = _select_current_mission(work_items)
    next_action = _build_next_action(
        current_mission=current_mission,
        pending_work=pending,
        high_risk_clusters=high_risk_clusters,
    )
    bitmap_status = str(bitmap_pipeline.get("status", "")).strip().lower()
    bitmap_next_text = str(bitmap_pipeline.get("next_action", "")).strip()
    is_bitmap_mission = bool(current_mission and "bitmap" in str(current_mission.get("title", "")).strip().lower())
    if bitmap_next_text and bitmap_status in {"critical", "warning"} and (current_mission is None or is_bitmap_mission):
        next_action = {
            "text": bitmap_next_text,
            "type": str(bitmap_pipeline.get("action_type", "")).strip() or "bitmap_action",
            "ref": str(bitmap_pipeline.get("action_ref", "")).strip() or "bitmap",
        }
    journey, reentry_minutes = _build_journey_summary(recent_events=recent_events, next_action=next_action)
    frozen_ideas = _build_frozen_ideas(session=session, project_name=project_name, limit=5)

    normalized_lock = str(focus_lock_level or "soft").strip().lower()
    if normalized_lock not in {"soft", "hard"}:
        normalized_lock = "soft"

    lock_reason = ""
    normalized_limit = max(1, int(wip_limit))
    if normalized_lock == "hard":
        if len(in_progress) > 0:
            lock_reason = f"HARD_LOCK_ACTIVE:{len(in_progress)}"
    elif len(in_progress) >= normalized_limit:
        lock_reason = f"WIP_LIMIT_REACHED:{len(in_progress)}/{normalized_limit}"
    elif current_mission is None:
        lock_reason = "NO_ACTIVE_MISSION"

    status_kor = {
        "READY": "준비됨",
        "IN_PROGRESS": "진행중",
        "DONE": "완료",
        "BLOCKED": "막힘",
        "FAILED": "실패",
    }
    mission_status = str(current_mission.get("status", "")).upper() if current_mission else ""
    mission_title = str(current_mission.get("title", "")).strip() if current_mission else ""
    sone_missing_count = int(sone_summary.get("missing_slot_count", 0) or 0)

    if current_mission and mission_status in {"BLOCKED", "FAILED"}:
        now_problem = f"{mission_title} 작업이 {status_kor.get(mission_status, '문제')} 상태입니다."
    elif sone_missing_count > 0:
        now_problem = f"SonE 검증 누락 슬롯 {sone_missing_count}건이 있습니다."
    elif str(bitmap_pipeline.get("status", "")).lower() == "critical":
        now_problem = "bitmap 검증 파이프라인 오류가 감지되었습니다."
    elif str(bitmap_pipeline.get("status", "")).lower() == "warning":
        now_problem = "bitmap 파이프라인 점검이 필요합니다."
    elif high_risk_clusters:
        top_cluster = high_risk_clusters[0]
        now_problem = f"질문 클러스터 {top_cluster.get('cluster_id', '-')} 판단이 필요합니다."
    elif pending:
        now_problem = "대기 작업이 남아 있습니다."
    else:
        now_problem = "치명 문제는 없습니다."

    if current_mission:
        now_building = f"{mission_title} ({status_kor.get(mission_status, mission_status or '진행중')})"
    elif pending:
        first = pending[0]
        now_building = f"{str(first.get('title', '')).strip() or str(first.get('id', '-'))} 준비 단계"
    else:
        now_building = "새 작업 준비"

    next_decision = str(next_action.get("text", "")).strip() or "다음 액션 없음"
    if sone_missing_count > 0 and current_mission is None:
        next_decision = str(sone_summary.get("validation_next_action", "")).strip() or next_decision

    return {
        "focus_mode": bool(focus_mode),
        "current_mission_id": str(current_mission.get("id", "")) if current_mission else None,
        "current_mission": current_mission or None,
        "next_action": next_action,
        "focus_lock": {
            "level": normalized_lock,
            "reason": lock_reason,
            "wip_limit": normalized_limit,
        },
        "active_mission_ids": [str(row.get("id", "")) for row in in_progress if str(row.get("id", "")).strip()],
        "frozen_ideas": frozen_ideas,
        "journey": journey,
        "metrics": {
            "wip_active_count": len(in_progress),
            "reentry_minutes": reentry_minutes,
        },
        "sone": {
            "validation_state": str(sone_summary.get("validation_state", "")).strip() or "unknown",
            "missing_slot_count": sone_missing_count,
            "next_action": str(sone_summary.get("validation_next_action", "")).strip(),
            "freshness_minutes": sone_summary.get("freshness_minutes"),
        },
        "human_summary": {
            "now_problem": now_problem,
            "now_building": now_building,
            "next_decision": next_decision,
        },
        "bitmap_pipeline": bitmap_pipeline,
    }


def _build_human_view(
    *,
    focus_payload: dict[str, Any],
    pending: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
    recent_events: list[dict[str, Any]],
    roadmap_journal: dict[str, Any],
    remaining_work: int,
) -> dict[str, Any]:
    summary = focus_payload.get("human_summary") if isinstance(focus_payload.get("human_summary"), dict) else {}
    now_problem = str(summary.get("now_problem", "")).strip() or "치명 문제는 없습니다."
    now_building = str(summary.get("now_building", "")).strip() or "진행 항목 없음"
    next_decision = str(summary.get("next_decision", "")).strip() or "다음 액션 없음"
    bitmap_pipeline = (
        focus_payload.get("bitmap_pipeline")
        if isinstance(focus_payload.get("bitmap_pipeline"), dict)
        else {"status": "healthy", "next_action": "bitmap 파이프라인 이상 없음"}
    )

    severity = "ok"
    if high_risk_clusters:
        severity = "warning"
    current_mission = focus_payload.get("current_mission") if isinstance(focus_payload.get("current_mission"), dict) else {}
    current_status = str(current_mission.get("status", "")).upper()
    if current_status in {"BLOCKED", "FAILED"}:
        severity = "danger"
    elif str(bitmap_pipeline.get("status", "")).lower() == "critical":
        severity = "danger"
    elif str(bitmap_pipeline.get("status", "")).lower() == "warning":
        severity = "warning"

    top_pending = [
        {
            "id": str(row.get("id", "")),
            "title": str(row.get("title", "")).strip() or str(row.get("id", "")),
            "status": str(row.get("status", "")).upper(),
        }
        for row in pending[:3]
    ]
    top_risks = [
        {
            "cluster_id": str(row.get("cluster_id", "")),
            "risk_score": float(row.get("risk_score", 0.0) or 0.0),
        }
        for row in high_risk_clusters[:3]
    ]
    recent = []
    for row in reversed(recent_events[-6:]):
        recent.append(
            {
                "event_type": str(row.get("event_type", "")).strip(),
                "summary": str(row.get("summary", "")).strip() or str(row.get("target", "")).strip(),
            }
        )
    journal_entries = (
        roadmap_journal.get("entries")
        if isinstance(roadmap_journal, dict) and isinstance(roadmap_journal.get("entries"), list)
        else []
    )
    current_phase = str((roadmap_journal or {}).get("current_phase", "")).strip()
    current_phase_step = str((roadmap_journal or {}).get("current_phase_step", "")).strip()
    if (not current_phase or not current_phase_step) and isinstance(journal_entries, list):
        for row in journal_entries:
            if not isinstance(row, dict):
                continue
            if not current_phase:
                current_phase = str(row.get("phase", "")).strip()
            if not current_phase_step:
                current_phase_step = str(row.get("phase_step", "")).strip()
            if current_phase and current_phase_step:
                break
    recorded_top = [
        {
            "id": str(row.get("id", "")).strip(),
            "title": str(row.get("title", "")).strip(),
            "summary": str(row.get("summary", "")).strip(),
            "category": str(row.get("category", "")).strip().upper(),
            "recorded_at": str(row.get("recorded_at", "")).strip(),
        }
        for row in journal_entries[:5]
        if isinstance(row, dict)
    ]
    return {
        "summary_cards": [
            {"key": "problem", "title": "지금 문제", "text": now_problem, "severity": severity},
            {"key": "building", "title": "지금 만드는 것", "text": now_building, "severity": "info"},
            {"key": "decision", "title": "다음 결정", "text": next_decision, "severity": "action"},
            {
                "key": "bitmap",
                "title": "Bitmap 상태",
                "text": str(bitmap_pipeline.get("next_action", "")).strip() or "bitmap 파이프라인 이상 없음",
                "severity": "warning" if str(bitmap_pipeline.get("status", "")).lower() != "healthy" else "ok",
            },
        ],
        "quick_lists": {
            "pending_top": top_pending,
            "risk_top": top_risks,
            "recent_top": recent,
            "recorded_top": recorded_top,
        },
        "roadmap_now": {
            "remaining_work": int(remaining_work),
            "high_risk_count": int(len(high_risk_clusters)),
            "current_mission_id": focus_payload.get("current_mission_id"),
            "next_action": str((focus_payload.get("next_action") or {}).get("text", "")).strip(),
            "bitmap_pipeline_status": str(bitmap_pipeline.get("status", "")).strip() or "healthy",
            "phase": current_phase or "1",
            "phase_step": current_phase_step or "1.0",
        },
    }


def _build_ai_view(
    *,
    project_name: str,
    focus_payload: dict[str, Any],
    module_overview: list[dict[str, Any]],
    high_risk_clusters: list[dict[str, Any]],
    progress_sync: dict[str, Any],
    roadmap_journal: dict[str, Any],
    bitmap_pipeline: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract": "canopy_ai_view.v0.1",
        "project": project_name,
        "focus": {
            "current_mission_id": focus_payload.get("current_mission_id"),
            "focus_lock": focus_payload.get("focus_lock"),
            "metrics": focus_payload.get("metrics"),
            "journey": focus_payload.get("journey"),
        },
        "module_overview": module_overview,
        "risk_clusters": high_risk_clusters[:10],
        "bitmap_pipeline": bitmap_pipeline,
        "progress_sync": progress_sync,
        "roadmap_journal": {
            "total": int((roadmap_journal or {}).get("total", 0) or 0),
            "last_recorded_at": str((roadmap_journal or {}).get("last_recorded_at", "")).strip(),
            "category_counts": (roadmap_journal or {}).get("category_counts", {}),
            "phase_counts": (roadmap_journal or {}).get("phase_counts", {}),
            "current_phase": str((roadmap_journal or {}).get("current_phase", "")).strip(),
            "current_phase_step": str((roadmap_journal or {}).get("current_phase_step", "")).strip(),
        },
    }


def _build_sync_status(
    *,
    recent_events: list[dict[str, Any]],
    progress_sync: dict[str, Any],
) -> dict[str, Any]:
    step_by_type = {
        "SYNC_HANDSHAKE_INIT": "handshake",
        "SYNC_PROGRESS_REPORTED": "progress",
        "SYNC_COMMIT_APPLIED": "commit",
        "SYNC_RECONCILED": "reconcile",
        "STATUS_SYNCED": "status_sync",
        "FOREST_STATUS_SYNCED": "status_sync",
        "ROADMAP_SYNCED": "roadmap_sync",
        "FOREST_ROADMAP_SYNCED": "roadmap_sync",
    }
    route_by_type = {
        "SYNC_HANDSHAKE_INIT": "sync-router",
        "SYNC_PROGRESS_REPORTED": "sync-router",
        "SYNC_COMMIT_APPLIED": "sync-router",
        "SYNC_RECONCILED": "sync-router",
        "STATUS_SYNCED": "status-sync",
        "FOREST_STATUS_SYNCED": "status-sync",
        "ROADMAP_SYNCED": "roadmap-sync",
        "FOREST_ROADMAP_SYNCED": "roadmap-sync",
    }
    latest: dict[str, Any] | None = None
    latest_type = ""
    for row in reversed(recent_events):
        event_type = str(row.get("event_type", "")).strip().upper()
        if event_type in step_by_type:
            latest = row
            latest_type = event_type
            break

    if latest is None:
        return {
            "state": "unknown",
            "label": "미동기화",
            "step": "none",
            "route_type": "unknown",
            "last_event_type": "",
            "last_at": "",
            "message": "동기화 이력이 없습니다.",
            "stale_minutes": None,
            "recorded": 0,
            "skipped": 0,
            "mismatch_count": 0,
        }

    payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
    summary = str(latest.get("summary", "")).strip()
    step = step_by_type.get(latest_type, "other")
    route_type = route_by_type.get(latest_type, "unknown")
    state = "ok"
    label = "정상"
    mismatch_count = int(payload.get("mismatch_count", 0) or 0)

    if latest_type == "SYNC_HANDSHAKE_INIT" and not bool(payload.get("allowed", True)):
        state = "blocked"
        label = "차단"
        code = str(payload.get("code", "")).strip()
        summary = f"핸드셰이크 차단{f' ({code})' if code else ''}"
    elif latest_type == "SYNC_COMMIT_APPLIED":
        commit_status = str(payload.get("commit_status", "")).strip().upper()
        if commit_status == "BLOCKED":
            state = "warning"
            label = "검증실패"
            summary = "커밋 검증 실패로 BLOCKED"
    elif latest_type == "SYNC_RECONCILED" and mismatch_count > 0:
        state = "warning"
        label = "불일치"
        summary = f"정합성 차이 {mismatch_count}건"

    recorded = int(payload.get("recorded", 0) or 0)
    skipped = int(payload.get("skipped", 0) or 0)
    if latest_type == "SYNC_RECONCILED":
        # reconcile payload does not have skipped; keep summary-level view stable.
        skipped = int(payload.get("skipped", 0) or 0)

    progress_state = str(progress_sync.get("status", "")).strip().lower()
    if state == "ok" and progress_state == "unsynced":
        state = "warning"
        label = "동기화필요"
        if not summary:
            summary = "progress snapshot 미동기화 상태"

    stale_minutes: int | None = None
    last_at_raw = str(latest.get("timestamp", "")).strip()
    parsed_last = _parse_iso_datetime(last_at_raw)
    if parsed_last is not None:
        stale_minutes = max(0, int((datetime.now(UTC) - parsed_last).total_seconds() // 60))
        if state == "ok" and stale_minutes >= 15:
            state = "warning"
            label = "지연"
            summary = summary or "최근 동기화가 오래되어 새로고침/동기화가 필요합니다."

    return {
        "state": state,
        "label": label,
        "step": step,
        "route_type": route_type,
        "last_event_type": latest_type,
        "last_at": str(latest.get("timestamp", "")).strip(),
        "message": summary or "동기화 상태 확인",
        "stale_minutes": stale_minutes,
        "recorded": recorded,
        "skipped": skipped,
        "mismatch_count": mismatch_count,
    }


def build_canopy_data(
    *,
    project_name: str,
    session,
    view: str = "focus",
    risk_threshold: float = 0.8,
    module_sort: str = "importance",
    event_filter: str = "all",
    limit: int = DEFAULT_CANOPY_LIMIT,
    offset: int = 0,
    module_filter: str = "all",
    focus_mode: bool = True,
    focus_lock_level: str = "soft",
    wip_limit: int = 1,
) -> dict[str, Any]:
    ensure_project_layout(project_name)
    page_limit, page_offset = _normalize_limit_offset(limit=limit, offset=offset)
    selected_module = str(module_filter or "all").strip().lower()
    selected_view = str(view or "focus").strip().lower()
    if selected_view not in CANOPY_VIEW_OPTIONS:
        selected_view = "focus"
    if selected_module not in {"all", *MODULE_ORDER}:
        selected_module = "all"

    raw_works = session.query(WorkPackage).order_by(WorkPackage.updated_at.desc(), WorkPackage.id.desc()).limit(1000).all()
    works = [row for row in raw_works if _project_name_for_work(row) == project_name]
    questions = (
        session.query(QuestionPool)
        .order_by(QuestionPool.risk_score.desc(), QuestionPool.hit_count.desc(), QuestionPool.cluster_id.asc())
        .all()
    )

    question_queue: list[dict[str, Any]] = []
    linked_node_risk: dict[str, float] = {}
    max_risk = 0.0
    high_risk_clusters: list[dict[str, Any]] = []

    for row in questions:
        linked_nodes = row.linked_nodes if isinstance(row.linked_nodes, list) else []
        risk_score = float(row.risk_score or 0.0)
        question_status = _question_status(str(row.status or ""))
        actionable = _is_question_actionable(question_status)
        max_risk = max(max_risk, risk_score)

        queue_row = {
            "cluster_id": row.cluster_id,
            "description": row.description,
            "status": question_status,
            "risk_score": risk_score,
            "hit_count": int(row.hit_count or 0),
            "linked_nodes": linked_nodes,
            "updated_at": _to_iso(row.updated_at),
        }
        question_queue.append(queue_row)

        if actionable and risk_score >= risk_threshold:
            high_risk_clusters.append(
                {
                    "cluster_id": row.cluster_id,
                    "risk_score": risk_score,
                    "hit_count": int(row.hit_count or 0),
                    "linked_nodes": linked_nodes,
                }
            )
        if actionable:
            for node in linked_nodes:
                key = str(node).strip().lower()
                if not key:
                    continue
                linked_node_risk[key] = max(linked_node_risk.get(key, 0.0), risk_score)

    work_items: list[dict[str, Any]] = []
    status_summary = {"READY": 0, "IN_PROGRESS": 0, "DONE": 0, "BLOCKED": 0, "FAILED": 0, "UNVERIFIED": 0}

    for row in works:
        linked_node = str(row.linked_node or "").strip().lower()
        linked_risk = linked_node_risk.get(linked_node, 0.0)
        item = _serialize_work_item(row, linked_risk)
        work_items.append(item)
        status = str(item["status"])
        status_summary[status] = status_summary.get(status, 0) + 1

    status_summary["UNVERIFIED"] = len(high_risk_clusters)

    bitmap_summary = build_bitmap_summary(session, days=7, limit=10)
    bitmap_metrics = bitmap_summary.get("metrics") if isinstance(bitmap_summary.get("metrics"), dict) else {}
    bitmap_lifecycle = (
        bitmap_summary.get("lifecycle") if isinstance(bitmap_summary.get("lifecycle"), dict) else {}
    )
    bitmap_health = {
        "window_days": int(bitmap_lifecycle.get("window_days", 7) or 7),
        "candidate_count_7d": int(bitmap_metrics.get("candidate_count_7d", 0) or 0),
        "pending_count": int(bitmap_lifecycle.get("pending_count", 0) or 0),
        "adoption_rate": float(bitmap_lifecycle.get("adoption_rate", 0.0) or 0.0),
        "invalid_count_7d": int(bitmap_metrics.get("invalid_count_7d", 0) or 0),
        "conflict_mark_count_7d": int(bitmap_metrics.get("conflict_mark_count_7d", 0) or 0),
        "duplicate_combined_groups": int(bitmap_metrics.get("duplicate_combined_groups", 0) or 0),
        "duplicate_backbone_rows": int(bitmap_metrics.get("duplicate_backbone_rows", 0) or 0),
    }
    bitmap_pipeline = _build_bitmap_pipeline_status(bitmap_health)

    module_overview = _build_module_overview(
        work_items=work_items,
        question_queue=question_queue,
        risk_threshold=float(risk_threshold),
        bitmap_health=bitmap_health,
    )
    module_overview = _sort_module_overview(module_overview, sort_by=module_sort)
    system_inventory = _build_system_inventory(
        module_overview=module_overview,
        high_risk_clusters=high_risk_clusters,
    )

    if selected_module == "all":
        filtered_work_items = work_items
        filtered_question_queue = question_queue
    else:
        filtered_work_items = [item for item in work_items if str(item.get("module", "")) == selected_module]
        filtered_question_queue = [
            row for row in question_queue if selected_module in _question_modules(row)
        ]
    topology = _build_connection_graph(
        module_overview=module_overview,
        work_items=filtered_work_items,
        question_queue=filtered_question_queue,
        risk_threshold=float(risk_threshold),
    )
    sone_summary = _build_sone_summary(project_name)
    recent_events_all = _read_recent_events(project_name, limit=80)
    recent_events_all.extend(_read_engine_bitmap_events(session, limit=80))
    recent_events_all = sorted(recent_events_all, key=lambda row: str(row.get("timestamp", "")))
    for row in recent_events_all:
        if "level" not in row:
            row["level"] = "info"
    recent_events = _filter_recent_events(recent_events_all, event_filter=event_filter)

    pending = [item for item in filtered_work_items if item["status"] in {"READY", "BLOCKED", "FAILED"}]
    in_progress = [item for item in filtered_work_items if item["status"] == "IN_PROGRESS"]
    done_recent = [item for item in filtered_work_items if item["status"] == "DONE"]

    pending = sorted(pending, key=lambda item: (-int(item["priority_score"]), str(item["updated_at"])))[:20]
    in_progress = sorted(in_progress, key=lambda item: (-int(item["priority_score"]), str(item["updated_at"])))[:20]
    done_recent = sorted(done_recent, key=lambda item: (str(item["updated_at"]), str(item["id"])), reverse=True)[:20]

    nodes_all: list[dict[str, Any]] = []
    nodes_all.extend(
        {
            "id": item["id"],
            "type": "work",
            "label": item["title"],
            "status": item["status"],
            "module": item["module"],
            "module_label": item["module_label"],
            "kind": item["kind"],
            "priority_score": item["priority_score"],
            "linked_risk": item["linked_risk"],
            "context_tag": item["context_tag"],
            "linked_node": item["linked_node"],
            "updated_at": item["updated_at"],
        }
        for item in filtered_work_items
    )
    nodes_all.extend(
        {
            "id": f"q_{row['cluster_id']}",
            "type": "question",
            "label": row["cluster_id"],
            "status": _question_node_status(
                status=row.get("status"),
                risk_score=float(row.get("risk_score", 0.0) or 0.0),
                risk_threshold=float(risk_threshold),
            ),
            "risk_score": row["risk_score"],
            "hit_count": row["hit_count"],
        }
        for row in filtered_question_queue
    )

    eta = _roadmap_eta_hint(works=works)
    recent_events_page, events_page_meta = _paginate_rows(recent_events, limit=page_limit, offset=page_offset)
    nodes_page, nodes_page_meta = _paginate_rows(nodes_all, limit=page_limit, offset=page_offset)
    question_queue_page, question_page_meta = _paginate_rows(
        filtered_question_queue, limit=page_limit, offset=page_offset
    )
    progress_sync = load_progress_snapshot(project_name=project_name)
    if progress_sync is None:
        progress_sync = {
            "status": "unsynced",
            "project": project_name,
            "hint": "status/sync 실행 전",
            "synced_at": "",
            "next_actions": [],
            "summary": {
                "work_total": len(filtered_work_items),
                "remaining_work": len([item for item in filtered_work_items if item["status"] != "DONE"]),
                "done_last_7d": eta["done_last_7d"],
                "eta_hint": eta["hint"],
            },
        }
    else:
        progress_sync = {"status": "synced", **progress_sync}
    roadmap_journal = read_roadmap_journal(project_name=project_name, limit=60)
    roadmap_entries = (
        roadmap_journal.get("entries")
        if isinstance(roadmap_journal.get("entries"), list)
        else []
    )
    parallel_workboard = _build_parallel_workboard(roadmap_entries=roadmap_entries)
    mind_workstream = _build_mind_workstream(session=session)

    virtual_plan_items = _build_virtual_plan_items(
        pending_work=pending,
        in_progress_work=in_progress,
        high_risk_clusters=high_risk_clusters,
        progress_sync=progress_sync,
        sone_summary=sone_summary,
        roadmap_entries=roadmap_entries,
    )
    pending_display = pending if pending else virtual_plan_items
    virtual_plan_count = len(virtual_plan_items)
    if virtual_plan_count > 0:
        module_overview = _apply_virtual_plan_to_module_overview(
            module_overview=module_overview,
            virtual_ready_count=virtual_plan_count,
            risk_threshold=float(risk_threshold),
        )
        module_overview = _sort_module_overview(module_overview, sort_by=module_sort)
        topology = _build_connection_graph(
            module_overview=module_overview,
            work_items=filtered_work_items,
            question_queue=filtered_question_queue,
            risk_threshold=float(risk_threshold),
        )

    sync_status = _build_sync_status(
        recent_events=recent_events_all,
        progress_sync=progress_sync,
    )

    focus_payload = _build_focus_payload(
        session=session,
        project_name=project_name,
        work_items=filtered_work_items,
        high_risk_clusters=high_risk_clusters,
        recent_events=recent_events,
        bitmap_pipeline=bitmap_pipeline,
        sone_summary=sone_summary,
        focus_mode=focus_mode,
        focus_lock_level=focus_lock_level,
        wip_limit=wip_limit,
    )
    # 남은 작업은 DONE 외 work + 미해결 고위험 질문 + (실제 작업이 0일 때) 다음 계획 1건을 포함한다.
    base_remaining_work = len([item for item in filtered_work_items if item["status"] != "DONE"]) + len(high_risk_clusters)
    virtual_remaining_work = len(virtual_plan_items) if (base_remaining_work == 0 and virtual_plan_items) else 0
    remaining_work = base_remaining_work + virtual_remaining_work
    human_view = _build_human_view(
        focus_payload=focus_payload,
        pending=pending_display,
        high_risk_clusters=high_risk_clusters,
        recent_events=recent_events,
        roadmap_journal=roadmap_journal,
        remaining_work=remaining_work,
    )
    ai_view = _build_ai_view(
        project_name=project_name,
        focus_payload=focus_payload,
        module_overview=module_overview,
        high_risk_clusters=high_risk_clusters,
        progress_sync=progress_sync,
        roadmap_journal=roadmap_journal,
        bitmap_pipeline=bitmap_pipeline,
    )

    return {
        "project": project_name,
        "view": selected_view,
        "generated_at": _to_iso(datetime.now(UTC)),
        "nodes": nodes_page,
        "status_summary": status_summary,
        "risk": {
            "threshold": risk_threshold,
            "max_risk_score": max_risk,
            "unverified_count": len(high_risk_clusters),
            "clusters": high_risk_clusters,
        },
        "module_overview": module_overview,
        "system_inventory": system_inventory,
        "roadmap": {
            "in_progress": in_progress,
            "pending": pending_display,
            "done_recent": done_recent,
            "total_work": len(filtered_work_items) + virtual_remaining_work,
            "remaining_work": remaining_work,
            "eta_hint": eta["hint"],
            "eta_days": eta["eta_days"],
            "done_last_7d": eta["done_last_7d"],
            "in_progress_count": eta["in_progress"],
            "blocked_count": eta["blocked"],
        },
        "sone_summary": sone_summary,
        "bitmap_health": bitmap_health,
        "bitmap_pipeline": bitmap_pipeline,
        "question_queue": question_queue_page,
        "topology": topology,
        "recent_events": recent_events_page,
        "progress_sync": progress_sync,
        "sync_status": sync_status,
        "focus": focus_payload,
        "roadmap_journal": roadmap_journal,
        "parallel_workboard": parallel_workboard,
        "mind_workstream": mind_workstream,
        "focus_mode": bool(focus_payload.get("focus_mode", True)),
        "current_mission_id": focus_payload.get("current_mission_id"),
        "next_action": focus_payload.get("next_action"),
        "focus_lock": focus_payload.get("focus_lock"),
        "frozen_ideas": focus_payload.get("frozen_ideas"),
        "journey": focus_payload.get("journey"),
        "metrics": focus_payload.get("metrics"),
        "human_view": human_view,
        "ai_view": ai_view,
        "filters": {
            "module_sort": module_sort if module_sort in MODULE_SORT_OPTIONS else "importance",
            "event_filter": event_filter if event_filter in EVENT_FILTER_OPTIONS else "all",
            "module": selected_module,
            "view": selected_view,
        },
        "pagination": {
            "nodes": nodes_page_meta,
            "question_queue": question_page_meta,
            "recent_events": events_page_meta,
        },
    }


def _mermaid_safe_id(node_id: str) -> str:
    return (
        node_id.replace("-", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _build_mermaid(topology: dict[str, Any]) -> str:
    nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    edges = topology.get("edges") if isinstance(topology.get("edges"), list) else []

    module_nodes = [node for node in nodes if node.get("type") == "module"]
    work_nodes = [node for node in nodes if node.get("type") == "work"]
    question_nodes = [node for node in nodes if node.get("type") == "question"]

    lines = ["flowchart LR", 'subgraph Modules["Modules"]']
    if module_nodes:
        for node in module_nodes:
            safe_id = _mermaid_safe_id(str(node.get("id", "")))
            label = str(node.get("label", ""))
            lines.append(f'{safe_id}["{label}"]:::MODULE')
    else:
        lines.append('module_none["No Modules"]:::MODULE')
    lines.append("end")

    lines.append('subgraph Work["Work Packages"]')
    if work_nodes:
        for node in work_nodes:
            safe_id = _mermaid_safe_id(str(node.get("id", "")))
            label = str(node.get("label", ""))
            status = str(node.get("status", "READY"))
            lines.append(f'{safe_id}["{label}"]:::{status}')
    else:
        lines.append('work_none["No Work"]:::READY')
    lines.append("end")

    lines.append('subgraph Questions["Risk Clusters"]')
    if question_nodes:
        for node in question_nodes:
            safe_id = _mermaid_safe_id(str(node.get("id", "")))
            label = str(node.get("label", ""))
            status = str(node.get("status", "READY"))
            lines.append(f'{safe_id}["{label}"]:::{status}')
    else:
        lines.append('question_none["No Risk Clusters"]:::DONE')
    lines.append("end")

    for edge in edges:
        src = _mermaid_safe_id(str(edge.get("from", "")))
        dst = _mermaid_safe_id(str(edge.get("to", "")))
        if src and dst:
            lines.append(f"{src} --> {dst}")

    lines.extend(
        [
            "classDef MODULE fill:#312e81,stroke:#a5b4fc,color:#e0e7ff;",
            "classDef READY fill:#1e3a8a,stroke:#93c5fd,color:#dbeafe;",
            "classDef IN_PROGRESS fill:#0f766e,stroke:#5eead4,color:#ccfbf1;",
            "classDef DONE fill:#14532d,stroke:#86efac,color:#dcfce7;",
            "classDef BLOCKED fill:#7f1d1d,stroke:#fca5a5,color:#fee2e2;",
            "classDef FAILED fill:#4c0519,stroke:#f9a8d4,color:#fce7f3;",
            "classDef UNVERIFIED fill:#78350f,stroke:#fcd34d,color:#fef3c7;",
        ]
    )
    return "\n".join(lines)


def _render_work_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty">항목 없음</div>'
    parts: list[str] = []
    for item in items:
        canopy_id = f"work:{str(item.get('id', '')).strip()}"
        parts.append(
            """
            <div class=\"mini-card trackable\" data-canopy-id=\"{canopy_id}\">
              <div class=\"mini-top\">
                <span class=\"badge\">{status}</span>
                <span class=\"score\">P{score}</span>
              </div>
              <p class=\"mini-title\">{title}</p>
              <p class=\"mini-sub\">{module} · {kind}</p>
              <p class=\"mini-sub\">{updated}</p>
            </div>
            """.format(
                canopy_id=canopy_id,
                status=str(item.get("status", "")),
                score=int(item.get("priority_score", 0) or 0),
                title=str(item.get("title", "")),
                module=str(item.get("module_label", item.get("module", ""))),
                kind=str(item.get("kind", "WORK")),
                updated=str(item.get("updated_at", "")) or "N/A",
            )
        )
    return "\n".join(parts)


def _render_module_cards(modules: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in modules:
        canopy_id = f"module:{str(row.get('module', '')).strip()}"
        bitmap_pressure = int(row.get("bitmap_pressure", 0) or 0)
        pressure_badge = ""
        if bitmap_pressure > 0:
            pressure_badge = f'<span class="pill">BITMAP +{bitmap_pressure}</span>'
        parts.append(
            """
            <div class=\"module-card trackable\" data-canopy-id=\"{canopy_id}\">
              <div class=\"module-top\">
                <h3>{label}</h3>
                <span class=\"importance\">중요도 {importance}</span>
              </div>
              <p class=\"module-progress\">진행률 {progress}%</p>
              <div class=\"row\">
                <span class=\"pill\">WORK {total}</span>
                <span class=\"pill\">DONE {done}</span>
                <span class=\"pill\">BLOCKED {blocked}</span>
                <span class=\"pill\">Q {pending_q}</span>
                {pressure_badge}
              </div>
              <p class=\"module-sub\">최근 갱신: {updated}</p>
            </div>
            """.format(
                canopy_id=canopy_id,
                label=row["label"],
                importance=int(row.get("importance", 0) or 0),
                progress=int(row.get("progress_pct", 0) or 0),
                total=int(row.get("work_total", 0) or 0),
                done=int(row.get("done", 0) or 0),
                blocked=int(row.get("blocked", 0) or 0),
                pending_q=int(row.get("pending_questions", 0) or 0),
                pressure_badge=pressure_badge,
                updated=str(row.get("last_updated_at", "")) or "N/A",
            )
        )
    return "\n".join(parts)


def _render_question_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='5'>질문 대기열이 비어 있습니다.</td></tr>"
    parts: list[str] = []
    for row in rows[:30]:
        canopy_id = f"question:{str(row.get('cluster_id', '')).strip()}"
        parts.append(
            "<tr class='trackable' data-canopy-id='{canopy_id}'><td>{cluster}</td><td>{risk:.2f}</td><td>{hit}</td><td>{status}</td><td>{nodes}</td></tr>".format(
                canopy_id=canopy_id,
                cluster=str(row.get("cluster_id", "")),
                risk=float(row.get("risk_score", 0.0) or 0.0),
                hit=int(row.get("hit_count", 0) or 0),
                status=str(row.get("status", "")),
                nodes=", ".join(str(node) for node in row.get("linked_nodes", [])[:3]) or "-",
            )
        )
    return "\n".join(parts)


def _render_event_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='4'>최근 이벤트가 없습니다.</td></tr>"
    parts: list[str] = []
    for row in rows[-30:]:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        summary = str(row.get("summary", "")).strip()
        if not summary:
            summary = str(payload.get("summary", "")).strip()
        parts.append(
            "<tr><td>{ts}</td><td>{event}</td><td>{target}</td><td>{summary}</td></tr>".format(
                ts=str(row.get("timestamp", "")),
                event=str(row.get("event_type", "")),
                target=str(row.get("target", "")),
                summary=summary or "-",
            )
        )
    return "\n".join(parts)


def _render_progress_sync(progress_sync: dict[str, Any]) -> str:
    status = str(progress_sync.get("status", "unsynced")).strip().lower()
    if status != "synced":
        return '<div class="empty">진행상태 동기화 전입니다. "진행상태 동기화"를 실행해 최신 로드맵을 저장하세요.</div>'

    summary = progress_sync.get("summary") if isinstance(progress_sync.get("summary"), dict) else {}
    next_actions = progress_sync.get("next_actions") if isinstance(progress_sync.get("next_actions"), list) else []
    synced_at = str(progress_sync.get("synced_at", "")).strip() or "N/A"
    eta_hint = str(summary.get("eta_hint", "")).strip() or "-"

    action_lines: list[str] = []
    for row in next_actions[:6]:
        if not isinstance(row, dict):
            continue
        action_lines.append(
            "<li><strong>[{priority}]</strong> {title} <span style='color:#9ca3af;'>- {reason}</span></li>".format(
                priority=str(row.get("priority", "P2")),
                title=str(row.get("title", "")),
                reason=str(row.get("reason", "")),
            )
        )
    if not action_lines:
        action_lines.append("<li>(항목 없음)</li>")

    return (
        "<div class='kv'>"
        f"<div class='k'>synced_at</div><div class='v'>{synced_at}</div>"
        f"<div class='k'>total_work</div><div class='v'>{int(summary.get('work_total', 0) or 0)}</div>"
        f"<div class='k'>remaining</div><div class='v'>{int(summary.get('remaining_work', 0) or 0)}</div>"
        f"<div class='k'>done_last_7d</div><div class='v'>{int(summary.get('done_last_7d', 0) or 0)}</div>"
        f"<div class='k'>eta_hint</div><div class='v'>{eta_hint}</div>"
        "</div>"
        "<p class='sub' style='margin-top:10px;'>다음 실행 항목</p>"
        f"<ul style='margin:8px 0 0 18px; padding:0; font-size:12px; line-height:1.5;'>{''.join(action_lines)}</ul>"
    )


def _render_html(data: dict[str, Any]) -> str:
    status_summary = data.get("status_summary", {})
    module_overview = data.get("module_overview", [])
    roadmap = data.get("roadmap", {})
    sone = data.get("sone_summary", {})
    bitmap = data.get("bitmap_health", {}) if isinstance(data.get("bitmap_health"), dict) else {}
    question_queue = data.get("question_queue", [])
    recent_events = data.get("recent_events", [])
    topology = data.get("topology", {})
    progress_sync = data.get("progress_sync") if isinstance(data.get("progress_sync"), dict) else {"status": "unsynced"}
    filters = data.get("filters", {}) if isinstance(data.get("filters"), dict) else {}
    mermaid = _build_mermaid(topology)

    return f"""<!doctype html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Sophia Forest Canopy</title>
  <script type=\"module\">
    import mermaid from \"https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs\";
    mermaid.initialize({{ startOnLoad: true, theme: \"dark\" }});
  </script>
  <style>
    :root {{
      --bg: #090f1f;
      --panel: #111827;
      --line: #25324a;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --blue: #60a5fa;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; }}
    .wrap {{ padding: 18px; display: grid; gap: 14px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px; }}
    .title {{ margin: 0 0 10px 0; font-size: 16px; font-weight: 700; }}
    .sub {{ margin: 0; font-size: 12px; color: var(--muted); }}
    .row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .pill {{ background: #0f172a; border: 1px solid #334155; border-radius: 999px; padding: 4px 10px; font-size: 12px; }}
    .grid-2 {{ display: grid; gap: 12px; grid-template-columns: 1.4fr 1fr; }}
    .grid-3 {{ display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .module-grid {{ display: grid; gap: 10px; grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .module-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 10px; }}
    .trackable.highlight {{ border-color: #f59e0b !important; box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.6) inset, 0 0 14px rgba(245, 158, 11, 0.35); }}
    tr.trackable.highlight td {{ background: rgba(245, 158, 11, 0.12); }}
    .module-top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
    .module-top h3 {{ margin: 0; font-size: 14px; }}
    .importance {{ font-size: 11px; color: #fbbf24; }}
    .module-progress {{ margin: 6px 0; font-weight: 700; color: #bfdbfe; }}
    .module-sub {{ margin: 6px 0 0 0; font-size: 11px; color: var(--muted); }}
    .mini-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 8px; }}
    .mini-top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }}
    .badge {{ font-size: 11px; border: 1px solid #475569; border-radius: 999px; padding: 2px 8px; color: #e2e8f0; }}
    .score {{ font-size: 11px; color: #fca5a5; }}
    .mini-title {{ margin: 0 0 6px 0; font-size: 13px; font-weight: 600; }}
    .mini-sub {{ margin: 0; font-size: 11px; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #25324a; text-align: left; font-size: 12px; padding: 7px 6px; vertical-align: top; }}
    th {{ color: #bfdbfe; font-weight: 600; }}
    .empty {{ font-size: 12px; color: var(--muted); border: 1px dashed #334155; border-radius: 8px; padding: 12px; text-align: center; }}
    .kv {{ display: grid; grid-template-columns: 130px 1fr; gap: 6px 10px; font-size: 12px; }}
    .k {{ color: #93c5fd; }}
    .v {{ color: #e2e8f0; }}
    @media (max-width: 1360px) {{
      .module-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid-2 {{ grid-template-columns: 1fr; }}
      .grid-3 {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <p class=\"title\">Sophia Forest Canopy</p>
      <div class=\"row\">
        <span class=\"pill\">READY: {status_summary.get("READY", 0)}</span>
        <span class=\"pill\">IN_PROGRESS: {status_summary.get("IN_PROGRESS", 0)}</span>
        <span class=\"pill\">DONE: {status_summary.get("DONE", 0)}</span>
        <span class=\"pill\">BLOCKED: {status_summary.get("BLOCKED", 0)}</span>
        <span class=\"pill\">FAILED: {status_summary.get("FAILED", 0)}</span>
        <span class=\"pill\">UNVERIFIED: {status_summary.get("UNVERIFIED", 0)}</span>
        <span class=\"pill\">SORT: {str(filters.get("module_sort", "importance")).upper()}</span>
        <span class=\"pill\">EVENTS: {str(filters.get("event_filter", "all")).upper()}</span>
      </div>
      <p class=\"sub\">설계·검토·현황 관제 전용 대시보드 · generated_at: {data.get("generated_at", "")}</p>
    </div>

    <div class=\"card\">
      <p class=\"title\">Module Overview</p>
      <div class=\"module-grid\">{_render_module_cards(module_overview)}</div>
    </div>

    <div class=\"grid-2\">
      <div class=\"card\">
        <p class=\"title\">Roadmap / Progress</p>
        <div class=\"row\">
          <span class=\"pill\">TOTAL_WORK: {roadmap.get("total_work", 0)}</span>
          <span class=\"pill\">REMAINING: {roadmap.get("remaining_work", 0)}</span>
          <span class=\"pill\">DONE_7D: {roadmap.get("done_last_7d", 0)}</span>
          <span class=\"pill\">ETA_DAYS: {roadmap.get("eta_days", "N/A")}</span>
        </div>
        <p class=\"sub\" style=\"margin-top:8px;\">{roadmap.get("eta_hint", "")}</p>
        <div class=\"grid-3\" style=\"margin-top:10px;\">
          <div>
            <p class=\"sub\" style=\"margin-bottom:8px;\">IN PROGRESS</p>
            {_render_work_cards(roadmap.get("in_progress", []))}
          </div>
          <div>
            <p class=\"sub\" style=\"margin-bottom:8px;\">PENDING / BLOCKED</p>
            {_render_work_cards(roadmap.get("pending", []))}
          </div>
          <div>
            <p class=\"sub\" style=\"margin-bottom:8px;\">DONE (RECENT)</p>
            {_render_work_cards(roadmap.get("done_recent", []))}
          </div>
        </div>
      </div>

      <div class=\"card\">
        <p class=\"title\">SonE Validation Summary</p>
        <div class=\"kv\">
          <div class=\"k\">source_doc</div><div class=\"v\">{sone.get("source_doc", "") or "N/A"}</div>
          <div class=\"k\">generated_at</div><div class=\"v\">{sone.get("generated_at", "") or "N/A"}</div>
          <div class=\"k\">missing_slots</div><div class=\"v\">{sone.get("missing_slot_count", 0)}</div>
          <div class=\"k\">impact_targets</div><div class=\"v\">{sone.get("impact_count", 0)}</div>
          <div class=\"k\">risk_clusters</div><div class=\"v\">{sone.get("risk_cluster_count", 0)}</div>
          <div class=\"k\">max_risk</div><div class=\"v\">{float(sone.get("max_risk_score", 0.0) or 0.0):.2f}</div>
          <div class=\"k\">dependency</div><div class=\"v\">nodes {sone.get("dependency", {}).get("node_count", 0)} / edges {sone.get("dependency", {}).get("edge_count", 0)}</div>
          <div class=\"k\">validation_stage</div><div class=\"v\">{sone.get("validation_stage", "heuristic_v0_1")}</div>
        </div>
        <p class=\"sub\" style=\"margin-top:10px;\">Missing Slots</p>
        <div style=\"max-height:180px; overflow:auto; font-size:12px;\">{json.dumps(sone.get("missing_slots", [])[:8], ensure_ascii=False, indent=2)}</div>
        <p class=\"sub\" style=\"margin-top:10px;\">Risk Reasons</p>
        <div style=\"max-height:180px; overflow:auto; font-size:12px;\">{json.dumps(sone.get("risk_reasons", [])[:8], ensure_ascii=False, indent=2)}</div>
      </div>
    </div>

    <div class=\"card\">
      <p class=\"title\">Bitmap Health (Storage Integrity)</p>
      <div class=\"row\">
        <span class=\"pill\">WINDOW: {bitmap.get("window_days", 7)}d</span>
        <span class=\"pill\">CANDIDATES: {bitmap.get("candidate_count_7d", 0)}</span>
        <span class=\"pill\">PENDING: {bitmap.get("pending_count", 0)}</span>
        <span class=\"pill\">ADOPTION: {float(bitmap.get("adoption_rate", 0.0) or 0.0) * 100:.0f}%</span>
      </div>
      <div class=\"kv\" style=\"margin-top:10px;\">
        <div class=\"k\">invalid_count_7d</div><div class=\"v\">{bitmap.get("invalid_count_7d", 0)}</div>
        <div class=\"k\">conflict_mark_count_7d</div><div class=\"v\">{bitmap.get("conflict_mark_count_7d", 0)}</div>
        <div class=\"k\">duplicate_groups</div><div class=\"v\">{bitmap.get("duplicate_combined_groups", 0)}</div>
        <div class=\"k\">duplicate_backbone_rows</div><div class=\"v\">{bitmap.get("duplicate_backbone_rows", 0)}</div>
      </div>
    </div>

    <div class=\"card\">
      <p class=\"title\">Project Progress Sync</p>
      {_render_progress_sync(progress_sync)}
    </div>

    <div class=\"card\">
      <p class=\"title\">Dependency / Execution Map</p>
      <div class=\"mermaid\">{mermaid}</div>
    </div>

    <div class=\"card\">
      <p class=\"title\">Question Queue</p>
      <table>
        <thead>
          <tr><th>Cluster</th><th>Risk</th><th>Hit</th><th>Status</th><th>Linked</th></tr>
        </thead>
        <tbody>
          {_render_question_rows(question_queue)}
        </tbody>
      </table>
    </div>

    <div class=\"card\">
      <p class=\"title\">Recent Change Log</p>
      <table>
        <thead>
          <tr><th>Timestamp</th><th>Event</th><th>Target</th><th>Summary</th></tr>
        </thead>
        <tbody>
          {_render_event_rows(recent_events)}
        </tbody>
      </table>
    </div>
  </div>
  <script>
    (function() {{
      const params = new URLSearchParams(window.location.search);
      const highlight = params.get("highlight");
      if (!highlight) return;
      const nodes = Array.from(document.querySelectorAll("[data-canopy-id]"));
      const matched = nodes.filter((node) => node.getAttribute("data-canopy-id") === highlight);
      if (!matched.length) return;
      matched.forEach((node) => node.classList.add("highlight"));
      const first = matched[0];
      if (first && typeof first.scrollIntoView === "function") {{
        first.scrollIntoView({{ behavior: "smooth", block: "center" }});
      }}
    }})();
  </script>
</body>
</html>
"""


def export_canopy_dashboard(*, project_name: str, data: dict[str, Any]) -> dict[str, Any]:
    ensure_project_layout(project_name)
    root = get_project_root(project_name)

    dashboard_path = root / "dashboard" / "index.html"
    dashboard_path.write_text(_render_html(data), encoding="utf-8")

    snapshot = {
        "project": project_name,
        "generated_at": data.get("generated_at", _to_iso(datetime.now(UTC))),
        "view": data.get("view", "focus"),
        "status_summary": data.get("status_summary", {}),
        "risk": data.get("risk", {}),
        "module_overview": data.get("module_overview", []),
        "system_inventory": data.get("system_inventory", []),
        "roadmap": data.get("roadmap", {}),
        "sone_summary": data.get("sone_summary", {}),
        "bitmap_health": data.get("bitmap_health", {}),
        "progress_sync": data.get("progress_sync", {}),
        "focus": data.get("focus", {}),
        "focus_mode": data.get("focus_mode", True),
        "current_mission_id": data.get("current_mission_id"),
        "next_action": data.get("next_action"),
        "focus_lock": data.get("focus_lock", {}),
        "frozen_ideas": data.get("frozen_ideas", {}),
        "journey": data.get("journey", {}),
        "metrics": data.get("metrics", {}),
        "human_view": data.get("human_view", {}),
        "roadmap_journal": data.get("roadmap_journal", {}),
        "question_queue": data.get("question_queue", []),
        "topology": data.get("topology", {}),
        "recent_events": data.get("recent_events", []),
        "nodes": data.get("nodes", []),
    }
    snapshot_path = root / "status" / "canopy_snapshot.json"
    write_json(snapshot_path, snapshot)
    return {
        "dashboard_path": str(dashboard_path),
        "snapshot_path": str(snapshot_path),
    }
