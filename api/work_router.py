from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.config import settings
from api.ledger_events import write_lifecycle_event
from api.sophia_notes import append_system_note
from core.engine.local_brain import build_notice
from core.ethics.gate import EthicsOutcome, GateInput, pre_commit_gate, pre_output_gate
from core.forest.canopy import build_canopy_data, export_canopy_dashboard
from core.forest.grove import analyze_to_forest
from core.forest.layout import append_project_ledger_event, ensure_project_layout
from core.services.focus_policy_service import evaluate_focus_policy
from core.services.forest_roadmap_sync_service import sync_roadmap_entries
from core.services.forest_status_service import sync_progress_snapshot
from core.services.question_signal_service import upsert_question_signal
from core.llm.generation_meta import attach_generation_meta, build_generation_meta, log_generation_line
from core.memory.schema import ChatTimelineMessage, WorkPackage, create_session_factory
from sophia_kernel.modules.mind_diary import ingest_trigger_event, maybe_build_daily_diary

router = APIRouter(prefix="/work", tags=["work"])
session_factory = create_session_factory(settings.db_path)

WORK_STATUSES = {"READY", "IN_PROGRESS", "DONE", "BLOCKED", "FAILED"}


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
    if raw in {"work", "memo", "roots", "question-queue", "system"}:
        return raw
    return "work"


def _normalize_status_filter(value: str | None) -> str:
    raw = (value or "READY").strip().upper()
    alias = {
        "READY": "READY",
        "IN_PROGRESS": "IN_PROGRESS",
        "ACKNOWLEDGED": "IN_PROGRESS",
        "DONE": "DONE",
        "COMPLETED": "DONE",
        "BLOCKED": "BLOCKED",
        "FAILED": "FAILED",
        "ALL": "ALL",
    }
    return alias.get(raw, "READY")


def _calc_importance(text: str) -> float:
    content = (text or "").strip()
    base = 0.45 + min(len(content) / 400.0, 0.25)
    if any(token in content.lower() for token in ["blocked", "failed", "긴급", "중요"]):
        base += 0.2
    return max(0.0, min(1.0, base))


def _derive_risk_level(text: str) -> Literal["none", "low", "med", "high"]:
    lowered = text.lower()
    if any(token in lowered for token in ["rm -rf", "drop table", "truncate", "delete ", "삭제", "파기", "format disk"]):
        return "high"
    if any(token in lowered for token in ["blocked", "failed", "위험", "리스크"]):
        return "med"
    if "?" in lowered:
        return "low"
    return "none"


def _apply_pre_output_ethics_text(content: str, context_tag: str, generation_meta: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    gate_input = GateInput(
        draft_text=content,
        task="reply",
        mode="chat",
        risk_level=_derive_risk_level(content),
        context_refs=[context_tag],
        capabilities={"web_access": False, "file_access": False, "exec_access": False},
        generation_meta=generation_meta,
        commit_allowed=False,
        commit_allowed_by="none",
        source="assistant",
        subject="reply",
        facet="CANDIDATE",
    )
    gate_result = pre_output_gate(gate_input)
    gate_payload = gate_result.model_dump(mode="json")

    adjusted = content
    if gate_result.outcome == EthicsOutcome.ADJUST and isinstance(gate_result.patch, dict):
        if gate_result.patch.get("kind") == "rewrite":
            candidate = str(gate_result.patch.get("content", "")).strip()
            if candidate:
                adjusted = candidate
    elif gate_result.outcome == EthicsOutcome.PENDING:
        adjusted = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
    elif gate_result.outcome == EthicsOutcome.BLOCK:
        adjusted = "요청은 현재 정책상 즉시 처리할 수 없습니다."

    if gate_payload.get("outcome") == EthicsOutcome.FIX.value:
        gate_payload["outcome"] = EthicsOutcome.PENDING.value
        gate_payload["reason_codes"] = ["INSUFFICIENT_EVIDENCE"]
        adjusted = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
    return adjusted, gate_payload


def _run_pre_commit_ethics(
    *,
    draft_text: str,
    context_refs: list[str],
    generation_meta: dict[str, Any],
    source: Literal["user", "assistant", "system"],
    subject: Literal["reply", "action", "rule", "summary", "decision"],
) -> dict[str, Any]:
    gate_input = GateInput(
        draft_text=draft_text,
        task="commit",
        mode="json",
        risk_level=_derive_risk_level(draft_text),
        context_refs=context_refs,
        capabilities={"file_access": True},
        generation_meta=generation_meta,
        commit_allowed=True,
        commit_allowed_by="policy",
        source=source,
        subject=subject,
        facet="CANDIDATE",
    )
    gate_result = pre_commit_gate(gate_input)
    payload = gate_result.model_dump(mode="json")
    if gate_result.outcome != EthicsOutcome.FIX or gate_result.commit_meta is None:
        reason = ",".join(gate_result.reason_codes or ["UNKNOWN"])
        raise HTTPException(status_code=409, detail=f"pre_commit_gate_blocked:{reason}")
    return payload


def _commit_with_ethics(
    *,
    session,
    endpoint: str,
    task: str,
    draft_text: str,
    context_refs: list[str],
    generation_meta: dict[str, Any],
    source: Literal["user", "assistant", "system"],
    subject: Literal["reply", "action", "rule", "summary", "decision"],
) -> dict[str, Any]:
    log_generation_line(generation_meta)
    commit_ethics = _run_pre_commit_ethics(
        draft_text=draft_text,
        context_refs=context_refs,
        generation_meta=generation_meta,
        source=source,
        subject=subject,
    )
    session.commit()
    write_lifecycle_event(
        "ETHICS_FIX_COMMITTED",
        {
            "project": "sophia",
            "endpoint": endpoint,
            "task": task,
            "provider_final": "local",
            "fallback_applied": False,
            "gate_reason": ",".join(commit_ethics.get("reason_codes", [])),
            "generation": generation_meta,
            "ethics": commit_ethics,
        },
        skill_id="ethics.gate",
    )
    return commit_ethics


def _save_system_message(
    *,
    session,
    content: str,
    context_tag: str = "system",
    linked_node: str | None = None,
    status: str = "normal",
) -> ChatTimelineMessage:
    normalized_context = _normalize_context_tag(context_tag)
    generation_meta = build_generation_meta(
        {
            "provider": "mock",
            "model": "work_router.notice",
            "route": "local",
            "capabilities": {
                "web_access": False,
                "file_access": False,
                "exec_access": False,
                "device_actions": False,
            },
            "latency_ms": 0,
        }
    )
    safe_content, output_ethics = _apply_pre_output_ethics_text(content, normalized_context, generation_meta)
    log_generation_line(generation_meta)
    row = ChatTimelineMessage(
        id=f"msg_{uuid4().hex}",
        role="sophia",
        content=safe_content,
        context_tag=normalized_context,
        importance=_calc_importance(safe_content),
        linked_cluster=None,
        linked_node=linked_node,
        meta=attach_generation_meta({"ethics": output_ethics}, generation_meta),
        status=status,
        created_at=_utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _default_return_payload_spec() -> dict[str, Any]:
    return {
        "work_package_id": "",
        "status": "DONE | BLOCKED | FAILED",
        "signals": [
            {
                "cluster_id": "",
                "risk_score": 0.0,
                "evidence": "",
            }
        ],
        "artifacts": [],
        "notes": "",
    }


def _render_packet_text(packet: dict[str, Any]) -> str:
    criteria = packet.get("acceptance_criteria", [])
    deliverables = packet.get("deliverables", [])
    lines = [
        f"WORK PACKAGE ID: {packet.get('id', '')}",
        f"KIND: {packet.get('kind', '')}",
        f"CONTEXT: {packet.get('context_tag', '')}",
        f"LINKED NODE: {packet.get('linked_node', '')}",
        "",
        "[Acceptance Criteria]",
    ]
    for item in criteria:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("[Deliverables]")
    for item in deliverables:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("[Return Payload Spec]")
    lines.append(str(packet.get("return_payload_spec", {})))
    return "\n".join(lines).strip()


def _build_packet(
    *,
    package_id: str,
    kind: str,
    context_tag: str,
    linked_node: str | None,
    acceptance_criteria: list[str],
    deliverables: list[str],
    return_payload_spec: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": package_id,
        "kind": kind,
        "context_tag": context_tag,
        "linked_node": linked_node,
        "acceptance_criteria": acceptance_criteria,
        "deliverables": deliverables,
        "return_payload_spec": return_payload_spec,
    }


def _serialize_package(row: WorkPackage) -> dict[str, Any]:
    payload = row.payload or {}
    packet = payload.get("work_packet")
    if not isinstance(packet, dict):
        packet = _build_packet(
            package_id=row.id,
            kind="ANALYZE",
            context_tag=row.context_tag,
            linked_node=row.linked_node,
            acceptance_criteria=[],
            deliverables=[],
            return_payload_spec=_default_return_payload_spec(),
        )
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "payload": payload,
        "work_packet": packet,
        "packet_text": _render_packet_text(packet),
        "context_tag": row.context_tag,
        "status": str(row.status or "READY").upper(),
        "linked_node": row.linked_node,
        "created_at": _to_iso(row.created_at),
        "acknowledged_at": _to_iso(row.acknowledged_at),
        "completed_at": _to_iso(row.completed_at),
        "updated_at": _to_iso(row.updated_at),
    }


def _coerce_string_list(value: list[str], fallback: list[str]) -> list[str]:
    out = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if out:
        return out
    return fallback


def _project_name_for_work(row: WorkPackage) -> str:
    payload = row.payload if isinstance(row.payload, dict) else {}
    project = payload.get("project") if isinstance(payload, dict) else None
    if isinstance(project, str) and project.strip():
        return project.strip().lower()
    return "sophia"


def _project_name_from_payload(payload: dict[str, Any] | None) -> str:
    source = payload or {}
    raw = source.get("project")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return "sophia"


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


def _sha256(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _event_dedup_key(work_id: str, report_hash: str, event_type: str) -> str:
    return f"{work_id}:{report_hash}:{event_type}"


def _reanalysis_skip_reason(*, seen_hashes: list[str], report_hash: str, within_debounce: bool) -> str:
    reasons: list[str] = []
    if report_hash in seen_hashes:
        reasons.append("duplicate_report_hash")
    if within_debounce:
        reasons.append("debounced_2s")
    if not reasons:
        reasons.append("unknown_skip")
    return "+".join(reasons)


def _safe_report_content(package_id: str, report_status: str, payload: "WorkReportPayload", title: str, linked_node: str | None) -> str:
    signal_rows = [
        f"- {signal.cluster_id} (risk={signal.risk_score}): {signal.evidence[:160]}"
        for signal in payload.signals
    ]
    artifacts = [f"- {item}" for item in payload.artifacts]
    lines: list[str] = [
        f"# IDE Report {package_id}",
        f"status: {report_status}",
        f"title: {title}",
        f"target: {linked_node or ''}",
        "",
        "## signals",
        "",
        "## artifacts",
        "",
        "## notes",
        payload.notes or "",
    ]
    signal_idx = lines.index("## signals") + 1
    if signal_rows:
        for row in signal_rows:
            lines.insert(signal_idx, row)
            signal_idx += 1
    else:
        lines.insert(signal_idx, "- none")

    artifact_idx = lines.index("## artifacts") + 1
    if artifacts:
        for row in artifacts:
            lines.insert(artifact_idx, row)
            artifact_idx += 1
    else:
        lines.insert(artifact_idx, "- none")
    return "\n".join(lines).strip()


def _record_live_roadmap_item(
    *,
    project_name: str,
    title: str,
    summary: str,
    category: str,
    tags: list[str] | None = None,
    note: str = "",
    files: list[str] | None = None,
) -> dict[str, Any]:
    item = {
        "title": str(title or "").strip(),
        "summary": str(summary or "").strip(),
        "files": [str(row).strip() for row in (files or []) if str(row).strip()],
        "tags": [str(row).strip() for row in (tags or []) if str(row).strip()],
        "category": str(category or "").strip(),
        "note": str(note or "").strip(),
    }
    if not item["title"]:
        return {"recorded": 0, "skipped": 1, "reason": "empty_title"}
    try:
        result = sync_roadmap_entries(
            project_name=project_name,
            items=[item],
            force_record=False,
            entry_type="LIVE_EVENT",
        )
        write_lifecycle_event(
            "FOREST_ROADMAP_LIVE_RECORDED",
            {
                "project": project_name,
                "title": item["title"][:120],
                "category": item["category"],
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
                "title": item["title"][:120],
                "category": item["category"],
                "error": str(exc)[:240],
            },
            skill_id="forest.roadmap",
        )
        return {"recorded": 0, "skipped": 1, "reason": "record_failed"}


class CreateWorkPackagePayload(BaseModel):
    kind: Literal["ANALYZE", "IMPLEMENT", "REVIEW", "MIGRATE"] = "ANALYZE"
    context_tag: str = "work"
    linked_node: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    return_payload_spec: dict[str, Any] = Field(default_factory=_default_return_payload_spec)
    title: str | None = None
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkSignal(BaseModel):
    cluster_id: str = Field(min_length=1, max_length=128)
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: str = ""
    linked_node: str | None = None


class WorkReportPayload(BaseModel):
    work_package_id: str | None = None
    status: Literal["DONE", "BLOCKED", "FAILED"]
    signals: list[WorkSignal] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    notes: str = ""


@router.post("/packages")
async def create_work_package(payload: CreateWorkPackagePayload):
    session = session_factory()
    try:
        now = _utc_now()
        package_id = f"wp_{uuid4().hex}"
        project_name = _project_name_from_payload(payload.payload)
        _enforce_focus_lock_for_work_mutation(
            session=session,
            project_name=project_name,
            operation="work.create_package",
        )
        context_tag = _normalize_context_tag(payload.context_tag)
        title = payload.title.strip() if isinstance(payload.title, str) and payload.title.strip() else f"{payload.kind} package"
        description = payload.description.strip() if isinstance(payload.description, str) and payload.description.strip() else None
        acceptance_criteria = _coerce_string_list(payload.acceptance_criteria, ["완료 보고 JSON 제출"])
        deliverables = _coerce_string_list(payload.deliverables, ["return_payload.json"])
        return_payload_spec = payload.return_payload_spec or _default_return_payload_spec()
        packet = _build_packet(
            package_id=package_id,
            kind=payload.kind,
            context_tag=context_tag,
            linked_node=payload.linked_node,
            acceptance_criteria=acceptance_criteria,
            deliverables=deliverables,
            return_payload_spec=return_payload_spec,
        )
        packet_text = _render_packet_text(packet)

        row = WorkPackage(
            id=package_id,
            title=title,
            description=description,
            payload={
                "work_packet": packet,
                "packet_text": packet_text,
                "legacy_payload": payload.payload or {},
                "project": project_name,
            },
            context_tag=context_tag,
            status="READY",
            linked_node=payload.linked_node,
            created_at=now,
            updated_at=now,
        )
        session.add(row)

        notice = build_notice("notice.ide_ready")
        _save_system_message(
            session=session,
            content=f"{notice}\n\n{packet_text}",
            context_tag="work",
            linked_node=payload.linked_node,
        )

        ingest_trigger_event(
            session,
            event_type="WORK_PACKAGE_CREATED",
            payload={
                "id": row.id,
                "kind": payload.kind,
                "context_tag": row.context_tag,
                "project": project_name,
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

        _commit_with_ethics(
            session=session,
            endpoint="/work/packages",
            task="work.create_package",
            draft_text=f"{package_id}|{payload.kind}|{context_tag}|{packet_text[:400]}",
            context_refs=[row.id, context_tag],
            generation_meta=build_generation_meta(
                {
                    "provider": "mock",
                    "model": "work_router.create_package",
                    "route": "local",
                    "capabilities": {
                        "web_access": False,
                        "file_access": True,
                        "exec_access": False,
                        "device_actions": False,
                    },
                    "latency_ms": 0,
                }
            ),
            source="system",
            subject="action",
        )
        session.refresh(row)

        write_lifecycle_event(
            "WORK_PACKAGE_CREATED",
            {
                "id": row.id,
                "project": _project_name_for_work(row),
                "kind": payload.kind,
                "context_tag": row.context_tag,
                "status": row.status,
            },
            skill_id="work.lifecycle",
        )
        _record_live_roadmap_item(
            project_name=_project_name_for_work(row),
            title=f"[work] {row.title} 생성",
            summary=f"{payload.kind} 패키지 생성 · context={row.context_tag}",
            category="FEATURE_ADD",
            tags=["work", "live", "create"],
            note=f"work_package_id:{row.id}",
        )
        return {"status": "ok", "package": _serialize_package(row)}
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@router.get("/packages")
async def list_work_packages(
    status: str = Query(default="READY"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    session = session_factory()
    try:
        status_key = _normalize_status_filter(status)
        query = session.query(WorkPackage)
        if status_key != "ALL":
            query = query.filter(WorkPackage.status == status_key)
        rows = query.order_by(WorkPackage.created_at.desc(), WorkPackage.id.desc()).limit(limit).all()
        return {"items": [_serialize_package(row) for row in rows]}
    finally:
        session.close()


@router.get("/packages/{package_id}/packet")
async def get_work_package_packet(package_id: str):
    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == package_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"work package not found: {package_id}")
        serialized = _serialize_package(row)
        return {
            "work_package_id": package_id,
            "packet": serialized["work_packet"],
            "packet_text": serialized["packet_text"],
        }
    finally:
        session.close()


@router.post("/packages/{package_id}/ack")
async def acknowledge_work_package(package_id: str):
    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == package_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"work package not found: {package_id}")
        status_changed = False
        if str(row.status).upper() == "READY":
            row.status = "IN_PROGRESS"
            row.acknowledged_at = _utc_now()
            row.updated_at = _utc_now()
            session.add(row)
            status_changed = True
        _commit_with_ethics(
            session=session,
            endpoint=f"/work/packages/{package_id}/ack",
            task="work.ack_package",
            draft_text=f"{row.id}|{row.status}|ack",
            context_refs=[row.id, row.context_tag],
            generation_meta=build_generation_meta(
                {
                    "provider": "mock",
                    "model": "work_router.ack",
                    "route": "local",
                    "capabilities": {
                        "web_access": False,
                        "file_access": True,
                        "exec_access": False,
                        "device_actions": False,
                    },
                    "latency_ms": 0,
                }
            ),
            source="system",
            subject="action",
        )
        if status_changed:
            _record_live_roadmap_item(
                project_name=_project_name_for_work(row),
                title=f"[work] {row.title} 시작",
                summary=f"작업 상태 전이 READY → {row.status}",
                category="SYSTEM_CHANGE",
                tags=["work", "live", "in_progress"],
                note=f"work_package_id:{row.id}",
            )
        return {"status": "ok", "package": _serialize_package(row)}
    finally:
        session.close()


@router.post("/packages/{package_id}/complete")
async def complete_work_package(package_id: str):
    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == package_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"work package not found: {package_id}")

        row.status = "DONE"
        if row.acknowledged_at is None:
            row.acknowledged_at = _utc_now()
        row.completed_at = _utc_now()
        row.updated_at = _utc_now()
        session.add(row)
        _commit_with_ethics(
            session=session,
            endpoint=f"/work/packages/{package_id}/complete",
            task="work.complete_package",
            draft_text=f"{row.id}|{row.status}|complete",
            context_refs=[row.id, row.context_tag],
            generation_meta=build_generation_meta(
                {
                    "provider": "mock",
                    "model": "work_router.complete",
                    "route": "local",
                    "capabilities": {
                        "web_access": False,
                        "file_access": True,
                        "exec_access": False,
                        "device_actions": False,
                    },
                    "latency_ms": 0,
                }
            ),
            source="system",
            subject="action",
        )
        session.refresh(row)

        write_lifecycle_event(
            "WORK_PACKAGE_COMPLETED",
            {
                "id": row.id,
                "project": _project_name_for_work(row),
                "context_tag": row.context_tag,
                "status": row.status,
            },
            skill_id="work.lifecycle",
        )
        _record_live_roadmap_item(
            project_name=_project_name_for_work(row),
            title=f"[work] {row.title} 완료",
            summary="작업 상태 전이 IN_PROGRESS → DONE",
            category="SYSTEM_CHANGE",
            tags=["work", "live", "done"],
            note=f"work_package_id:{row.id}",
        )
        return {"status": "ok", "package": _serialize_package(row)}
    finally:
        session.close()


@router.post("/packages/{package_id}/report")
async def submit_work_report(
    package_id: str,
    payload: WorkReportPayload,
    force_canopy_export: bool = Query(default=False),
):
    session = session_factory()
    try:
        row = session.query(WorkPackage).filter(WorkPackage.id == package_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"work package not found: {package_id}")
        if payload.work_package_id and payload.work_package_id != package_id:
            raise HTTPException(status_code=400, detail="work_package_id mismatch")

        project_name = _project_name_for_work(row)
        ensure_project_layout(project_name)

        report_status = payload.status
        row.status = report_status
        if row.acknowledged_at is None:
            row.acknowledged_at = _utc_now()
        if report_status == "DONE":
            row.completed_at = _utc_now()
        row.updated_at = _utc_now()

        pending_messages = []
        for signal in payload.signals:
            cluster_id = signal.cluster_id.strip()
            if not cluster_id:
                continue
            _, pending = upsert_question_signal(
                session=session,
                cluster_id=cluster_id,
                description=f"IDE signal: {cluster_id}",
                risk_score=float(signal.risk_score),
                snippet=(signal.evidence or "")[:200],
                source=f"work.report:{package_id}",
                evidence_timestamp=_to_iso(_utc_now()),
                linked_node=signal.linked_node or row.linked_node,
            )
            if pending is not None:
                pending_messages.append(pending.id)

        report_payload = {
            "work_package_id": package_id,
            "status": report_status,
            "signals": [signal.model_dump() for signal in payload.signals],
            "artifacts": payload.artifacts,
            "notes": payload.notes,
            "received_at": _to_iso(_utc_now()),
        }
        merged_payload = dict(row.payload or {})

        report_hash = _sha256(report_payload)
        reanalysis = merged_payload.get("reanalysis") if isinstance(merged_payload.get("reanalysis"), dict) else {}
        seen_hashes = list(reanalysis.get("seen_hashes", []))
        last_at_raw = str(reanalysis.get("last_at", "")).strip()
        last_at = None
        if last_at_raw:
            try:
                parsed = last_at_raw.replace("Z", "+00:00")
                last_at = datetime.fromisoformat(parsed)
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=UTC)
                last_at = last_at.astimezone(UTC)
            except ValueError:
                last_at = None

        now = _utc_now()
        within_debounce = False
        if last_at is not None:
            within_debounce = (now - last_at).total_seconds() < 2.0
        run_reanalysis = report_hash not in seen_hashes and not within_debounce
        reanalysis_skip_reason = (
            ""
            if run_reanalysis
            else _reanalysis_skip_reason(seen_hashes=seen_hashes, report_hash=report_hash, within_debounce=within_debounce)
        )
        run_canopy_export = run_reanalysis or force_canopy_export

        before_max_risk = 0.0
        if run_canopy_export:
            before_canopy = build_canopy_data(project_name=project_name, session=session)
            before_max_risk = float(before_canopy.get("risk", {}).get("max_risk_score", 0.0))

        analysis_result = None
        if run_reanalysis:
            report_content = _safe_report_content(
                package_id=package_id,
                report_status=report_status,
                payload=payload,
                title=row.title,
                linked_node=row.linked_node,
            )
            analysis_result = analyze_to_forest(
                project_name=project_name,
                doc_name=f"report_{package_id}_{now.strftime('%Y%m%d_%H%M%S')}.md",
                content=report_content,
                target=row.linked_node or row.id,
                change=f"IDE report {report_status}",
                scope="",
                write_doc=False,
            )
            for signal in analysis_result.get("signals", []):
                _, pending = upsert_question_signal(
                    session=session,
                    cluster_id=str(signal["cluster_id"]),
                    description=str(signal["description"]),
                    risk_score=float(signal["risk_score"]),
                    snippet=f"report:{package_id}",
                    source=f"forest.grove:{package_id}",
                    evidence_timestamp=_to_iso(now),
                    linked_node=row.linked_node,
                )
                if pending is not None:
                    pending_messages.append(pending.id)

            seen_hashes.append(report_hash)
            seen_hashes = seen_hashes[-50:]
            reanalysis = {
                "last_hash": report_hash,
                "last_at": _to_iso(now),
                "seen_hashes": seen_hashes,
            }

        canopy_data: dict[str, Any] | None = None
        export_info: dict[str, str] | None = None
        risk_increased = False
        if run_canopy_export:
            canopy_data = build_canopy_data(project_name=project_name, session=session)
            export_info = export_canopy_dashboard(project_name=project_name, data=canopy_data)
            after_max_risk = float(canopy_data.get("risk", {}).get("max_risk_score", 0.0))
            risk_increased = after_max_risk > before_max_risk

        auto_sync_enabled = bool(getattr(settings, "forest_auto_sync", False))
        auto_sync_ran = False
        auto_sync_snapshot_path = ""
        auto_sync_roadmap_path = ""
        if auto_sync_enabled and run_reanalysis and report_status in {"DONE", "BLOCKED", "FAILED"} and canopy_data is not None:
            synced = sync_progress_snapshot(project_name=project_name, canopy_data=canopy_data)
            if isinstance(synced.get("snapshot"), dict):
                canopy_data["progress_sync"] = {"status": "synced", **dict(synced["snapshot"])}
            auto_sync_ran = True
            auto_sync_snapshot_path = str(synced.get("snapshot_path", ""))
            auto_sync_roadmap_path = str(synced.get("roadmap_path", ""))
            append_project_ledger_event(
                project_name=project_name,
                event_type="STATUS_SYNCED",
                target=project_name,
                summary=f"auto status sync after report:{package_id}",
                payload={
                    "work_id": row.id,
                    "report_status": report_status,
                    "remaining_work": int((canopy_data.get("roadmap") or {}).get("remaining_work", 0) or 0),
                    "auto_sync": True,
                },
            )

        dedup_keys = list(merged_payload.get("event_dedup_keys", []))
        events_to_emit: list[tuple[str, dict[str, Any], str]] = []

        def queue_event(event_type: str, payload_obj: dict[str, Any], skill_id: str) -> bool:
            key = _event_dedup_key(package_id, report_hash, event_type)
            if key in dedup_keys:
                return False
            dedup_keys.append(key)
            events_to_emit.append((event_type, payload_obj, skill_id))
            return True

        queue_event(
            "WORK_PACKAGE_REPORTED",
            {
                "id": row.id,
                "project": project_name,
                "report_status": report_status,
                "work_status": row.status,
                "signals": len(payload.signals),
                "pending_question_messages": pending_messages,
                "reanalysis_ran": run_reanalysis,
                "reanalysis_skip_reason": reanalysis_skip_reason,
                "canopy_dashboard_path": export_info["dashboard_path"] if export_info else "",
            },
            "work.lifecycle",
        )
        if run_reanalysis:
            queue_event(
                "GROVE_ANALYZED",
                {
                    "id": row.id,
                    "project": project_name,
                    "report_status": report_status,
                    "signals": len(analysis_result.get("signals", []) if isinstance(analysis_result, dict) else []),
                    "source_doc": f"report:{package_id}",
                },
                "forest.grove",
            )
        if run_canopy_export and export_info is not None and canopy_data is not None:
            queue_event(
                "CANOPY_EXPORTED",
                {
                    "id": row.id,
                    "project": project_name,
                    "dashboard_path": export_info["dashboard_path"],
                    "status_summary": canopy_data.get("status_summary", {}),
                },
                "forest.canopy",
            )
        if auto_sync_ran:
            queue_event(
                "FOREST_STATUS_SYNCED",
                {
                    "id": row.id,
                    "project": project_name,
                    "work_id": row.id,
                    "report_status": report_status,
                    "snapshot_path": auto_sync_snapshot_path,
                    "roadmap_path": auto_sync_roadmap_path,
                    "auto_sync": True,
                },
                "forest.status",
            )

        merged_payload["last_report"] = report_payload
        merged_payload["reanalysis"] = reanalysis
        merged_payload["event_dedup_keys"] = dedup_keys[-500:]
        row.payload = merged_payload
        session.add(row)

        if run_canopy_export:
            _save_system_message(
                session=session,
                content="주인님, IDE 완료 보고가 도착했습니다.\n현황판을 갱신했습니다.",
                context_tag="work",
                linked_node=row.linked_node,
            )
        else:
            _save_system_message(
                session=session,
                content=f"주인님, IDE 완료 보고가 도착했습니다.\n재분석/현황판 갱신을 건너뛰었습니다. 사유: {reanalysis_skip_reason}",
                context_tag="work",
                linked_node=row.linked_node,
            )
        if risk_increased:
            _save_system_message(
                session=session,
                content="주인님, 이번 변경으로 위험 점수가 상승했습니다.\n확인이 필요합니다.",
                context_tag="question-queue",
                linked_node=row.linked_node,
            )
        if auto_sync_ran:
            _save_system_message(
                session=session,
                content="주인님, 보고 반영 직후 진행상태 로드맵을 자동 동기화했습니다.",
                context_tag="forest:canopy",
                linked_node=row.linked_node,
            )

        done_count = session.query(WorkPackage).filter(WorkPackage.status == "DONE").count()
        total_count = session.query(WorkPackage).count()
        if total_count > 0 and done_count == total_count:
            _save_system_message(
                session=session,
                content="주인님, 현재 모든 작업이 완료 상태입니다.",
                context_tag="work",
                linked_node=row.linked_node,
            )

        status_badge = "INFO"
        if report_status == "FAILED":
            status_badge = "RISK_HIGH"
        elif report_status == "BLOCKED":
            status_badge = "QUESTION_READY"
        elif payload.artifacts:
            status_badge = "ACTION_SUGGESTED"

        source_events = ["WORK_PACKAGE_REPORTED"]
        if run_reanalysis:
            source_events.append("GROVE_ANALYZED")
        if run_canopy_export:
            source_events.append("CANOPY_EXPORTED")

        note_summary = f"{row.title}: {report_status} 보고가 반영되었습니다."
        note_lines = [
            f"- work_id: {row.id}",
            f"- report_status: {report_status}",
            f"- signals: {len(payload.signals)}",
            f"- artifacts: {len(payload.artifacts)}",
            f"- reanalysis_ran: {str(run_reanalysis).lower()}",
            f"- reanalysis_skip_reason: {reanalysis_skip_reason or '-'}",
            f"- canopy_exported: {str(run_canopy_export).lower()}",
        ]
        append_system_note(
            db=session,
            note_type="WORK_REPORT_DIGEST",
            source_events=source_events,
            summary=note_summary,
            body_markdown="\n".join(note_lines),
            status="ACTIVE",
            actionables=[
                {"type": "view_work_package", "work_id": row.id},
                {"type": "review_report", "work_id": row.id},
            ],
            risk_score=max([float(signal.risk_score) for signal in payload.signals], default=0.0),
            badge=status_badge,
            dedup_key=f"work_report:{row.id}:{report_hash}",
        )

        _commit_with_ethics(
            session=session,
            endpoint=f"/work/packages/{package_id}/report",
            task="work.submit_report",
            draft_text=json.dumps(
                {
                    "work_id": row.id,
                    "status": report_status,
                    "signals": len(payload.signals),
                    "artifacts": len(payload.artifacts),
                    "reanalysis_ran": run_reanalysis,
                    "reanalysis_skip_reason": reanalysis_skip_reason,
                    "canopy_exported": run_canopy_export,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            context_refs=[row.id, row.context_tag, project_name],
            generation_meta=build_generation_meta(
                {
                    "provider": "mock",
                    "model": "work_router.report",
                    "route": "local",
                    "capabilities": {
                        "web_access": False,
                        "file_access": True,
                        "exec_access": False,
                        "device_actions": False,
                    },
                    "latency_ms": 0,
                }
            ),
            source="system",
            subject="summary",
        )
        session.refresh(row)

        for event_type, event_payload, skill_id in events_to_emit:
            write_lifecycle_event(event_type, event_payload, skill_id=skill_id)

        report_category = "SYSTEM_CHANGE"
        if report_status in {"BLOCKED", "FAILED"}:
            report_category = "PROBLEM_FIX"
        _record_live_roadmap_item(
            project_name=project_name,
            title=f"[work] {row.title} 보고 {report_status}",
            summary=(
                f"signals={len(payload.signals)} · "
                f"reanalysis={str(run_reanalysis).lower()} · "
                f"canopy={str(run_canopy_export).lower()}"
            ),
            category=report_category,
            tags=["work", "live", f"status:{report_status.lower()}"],
            note=f"work_package_id:{row.id}",
        )
        return {
            "status": "ok",
            "package": _serialize_package(row),
            "pending_question_messages": pending_messages,
            "reanalysis_ran": run_reanalysis,
            "reanalysis_skip_reason": reanalysis_skip_reason,
            "canopy_exported": run_canopy_export,
            "auto_sync_enabled": auto_sync_enabled,
            "auto_sync_ran": auto_sync_ran,
            "progress_snapshot_path": auto_sync_snapshot_path,
            "progress_roadmap_path": auto_sync_roadmap_path,
            "canopy": canopy_data or {},
            "canopy_dashboard_path": export_info["dashboard_path"] if export_info else "",
            "duplicate_or_debounced": not run_reanalysis,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()
