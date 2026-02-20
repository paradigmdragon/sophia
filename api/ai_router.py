from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.config import settings
from api.ledger_events import write_lifecycle_event
from core.ai.ai_router import AIRouterService
from core.ai.echo_guard import contains_sensitive_echo
from core.ai.redaction import redact_data, sha256_text
from core.ethics.gate import EthicsOutcome, GateInput, pre_commit_gate, pre_output_gate
from core.llm.generation_meta import attach_generation_meta, build_generation_meta, log_generation_line
from core.memory.schema import MindItem, MindWorkingLog, create_session_factory

router = APIRouter(prefix="/ai", tags=["ai"])
_SessionLocal = create_session_factory(settings.db_path)
_ai_service = AIRouterService(
    provider_default=settings.ai_provider_default,
    mode=settings.ai_mode,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _merge_unique(items: list[str], extras: list[str]) -> list[str]:
    out = [str(item).strip() for item in items if str(item).strip()]
    for extra in extras:
        value = str(extra).strip()
        if not value or value in out:
            continue
        out.append(value)
    return out


def _normalize_quality_state(value: str) -> str:
    key = (value or "").strip().upper()
    if key not in {"NORMAL", "FALLBACK", "SANITIZED"}:
        return "NORMAL"
    return key


def _apply_quality_tag(tags: list[str], quality_state: str) -> list[str]:
    quality = _normalize_quality_state(quality_state).lower()
    base = [str(item).strip() for item in tags if str(item).strip() and not str(item).startswith("quality:")]
    base.append(f"quality:{quality}")
    return base


def _line_80(value: str) -> str:
    return " ".join((value or "").split())[:80]


def _save_working_log(db, *, event_type: str, item_id: str, line: str) -> None:
    db.add(
        MindWorkingLog(
            line=_line_80(line),
            event_type=event_type,
            item_id=item_id,
            delta_priority=0,
            created_at=_utc_now(),
        )
    )
    db.flush()


def _serialize_mind_item(row: MindItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "summary_120": row.summary_120,
        "priority": int(row.priority or 0),
        "risk_score": float(row.risk_score or 0.0),
        "confidence": float(row.confidence or 0.0),
        "linked_bits": list(row.linked_bits or []),
        "tags": list(row.tags or []),
        "source_events": list(row.source_events or []),
        "status": row.status,
        "created_at": _to_iso(row.created_at),
        "updated_at": _to_iso(row.updated_at),
    }


def _upsert_mind_candidate(
    db,
    *,
    item_id: str,
    item_type: str,
    title: str,
    summary: str,
    tags: list[str],
    source_event: str,
    quality_state: str,
    linked_bits: list[str] | None = None,
    risk_score: float = 0.0,
    confidence: float = 0.6,
) -> dict[str, Any]:
    now = _utc_now()
    linked_bits = linked_bits or []
    row = db.query(MindItem).filter(MindItem.id == item_id).one_or_none()

    quality_tags = _apply_quality_tag(tags, quality_state)[:20]

    if row is None:
        row = MindItem(
            id=item_id,
            type=item_type,
            title=title[:255],
            summary_120=summary[:120] or "unknown",
            priority=45,
            risk_score=max(0.0, min(1.0, float(risk_score))),
            confidence=max(0.0, min(1.0, float(confidence))),
            linked_bits=linked_bits[:20],
            tags=quality_tags,
            source_events=[source_event],
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        _save_working_log(db, event_type=source_event, item_id=row.id, line=f"[{now.strftime('%H:%M')}] AI 후보 생성")
        return _serialize_mind_item(row)

    row.type = item_type
    row.title = title[:255]
    row.summary_120 = summary[:120] or "unknown"
    row.risk_score = max(float(row.risk_score or 0.0), max(0.0, min(1.0, float(risk_score))))
    row.confidence = max(float(row.confidence or 0.0), max(0.0, min(1.0, float(confidence))))
    row.tags = _merge_unique(_apply_quality_tag(list(row.tags or []), quality_state), quality_tags)[:20]
    row.linked_bits = _merge_unique(list(row.linked_bits or []), linked_bits)[:20]
    row.source_events = _merge_unique(list(row.source_events or []), [source_event])
    row.updated_at = now
    if row.status not in {"active", "parked", "done"}:
        row.status = "active"
    db.add(row)
    db.flush()
    _save_working_log(db, event_type=source_event, item_id=row.id, line=f"[{now.strftime('%H:%M')}] AI 후보 갱신")
    return _serialize_mind_item(row)


class IngestRequest(BaseModel):
    text: str
    source: str = "manual"
    context_tag_hint: str | None = None
    provider: str | None = None
    mode: str | None = None
    project: str = "sophia"


class TranscriptProcessRequest(BaseModel):
    text: str
    source: str = "manual"
    provider: str | None = None
    mode: str | None = None
    project: str = "sophia"


class RulesCandidatesRequest(BaseModel):
    text_bundle: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    provider: str | None = None
    mode: str | None = None
    project: str = "sophia"


class DiffSummarizeRequest(BaseModel):
    before_text: str = ""
    after_text: str = ""
    doc_path: str = ""
    provider: str | None = None
    mode: str | None = None
    project: str = "sophia"


def _make_response(
    *,
    task: str,
    result: dict[str, Any],
    contract_redacted: dict[str, Any],
    redacted_fields: list[str],
    mind_item: dict[str, Any],
    quality_state: str,
    generation_meta: dict[str, Any],
) -> dict[str, Any]:
    meta = dict(result.get("meta", {}))
    gate = dict(result.get("gate", {}))
    contract_out, output_ethics = _apply_pre_output_ethics_contract(
        task=task,
        contract_redacted=contract_redacted,
        generation_meta=generation_meta,
    )
    meta["redacted_fields"] = sorted(set([*meta.get("redacted_fields", []), *redacted_fields]))
    meta["quality_state"] = _normalize_quality_state(quality_state)
    meta["ethics"] = output_ethics
    meta = attach_generation_meta(meta, generation_meta)
    log_generation_line(generation_meta)
    return {
        "status": "ok",
        "task": task,
        "contract": contract_out,
        "meta": meta,
        "gate": gate,
        "mind_item": mind_item,
    }


def _safe_project(value: str) -> str:
    text = (value or "").strip().lower()
    return text or "sophia"


def _ensure_non_empty_text(value: str) -> None:
    if not str(value or "").strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "AI_EMPTY_INPUT", "message": "text is empty"},
        )


def _sanitize_summary_for_storage(
    *,
    input_text: str,
    summary_text: str,
    input_hash: str,
    input_len: int,
    source: str,
    quality_state: str,
) -> tuple[str, str]:
    raw_summary = str(summary_text or "")
    summary_redacted, summary_redacted_fields = redact_data(raw_summary)
    safe_summary = str(summary_redacted or "").strip()
    next_quality = _normalize_quality_state(quality_state)
    if summary_redacted_fields:
        next_quality = "SANITIZED"

    if contains_sensitive_echo(input_text, raw_summary):
        digest = input_hash.split(":", 1)[1] if ":" in input_hash else input_hash
        safe_summary = f"요약(비공개): {digest[:18]} len={input_len} source={source}"
        next_quality = "SANITIZED"

    return safe_summary[:120] or "unknown", next_quality


def _build_ai_event_payload(
    *,
    endpoint: str,
    task: str,
    project: str,
    schema: str,
    input_hash: str,
    input_len: int,
    provider_final: str,
    fallback_applied: bool,
    gate_reason: str,
    attempts_count: int,
    quality_state: str,
    mind_item_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "project": project,
        "task": task,
        "endpoint": endpoint,
        "schema": schema,
        "input_hash": input_hash,
        "input_len": int(max(0, input_len)),
        "provider_final": provider_final,
        "fallback_applied": bool(fallback_applied),
        "gate_reason": gate_reason,
        "attempts_count": int(max(0, attempts_count)),
        "quality_state": _normalize_quality_state(quality_state),
        "mind_item_id": mind_item_id,
    }
    for key, value in (extra or {}).items():
        payload[str(key)] = value
    return payload


def _build_router_generation_meta(*, result_meta: dict[str, Any], latency_ms: int = 0) -> dict[str, Any]:
    provider_final = str(result_meta.get("provider_final", "") or "unknown").strip().lower()
    route = "local"
    if provider_final in {"foundation", "apple"}:
        route = "os"
    elif provider_final == "openai":
        route = "server"

    return build_generation_meta(
        {
            "provider": provider_final,
            "model": str(result_meta.get("model", "unknown") or "unknown"),
            "route": route,
            "capabilities": {
                "web_access": False,
                "file_access": False,
                "exec_access": False,
                "device_actions": provider_final in {"foundation", "apple"},
            },
            "latency_ms": int(max(0, latency_ms)),
            "tokens_in": result_meta.get("tokens_in"),
            "tokens_out": result_meta.get("tokens_out"),
            "trace_id": result_meta.get("trace_id"),
        }
    )


def _derive_risk_level(text: str) -> Literal["none", "low", "med", "high"]:
    lowered = text.lower()
    if any(token in lowered for token in ["rm -rf", "drop table", "truncate", "delete ", "삭제", "파기", "format disk"]):
        return "high"
    if any(token in lowered for token in ["latest", "최신", "today", "현재", "risk", "리스크"]):
        return "med"
    if "?" in lowered:
        return "low"
    return "none"


def _apply_pre_output_ethics_contract(
    *,
    task: str,
    contract_redacted: dict[str, Any],
    generation_meta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_out = dict(contract_redacted)
    summary_key_map = {
        "ingest": "summary_120",
        "transcript": "summary",
        "diff": "diff_summary",
    }
    summary_key = summary_key_map.get(task, "")
    draft_text = str(contract_out.get(summary_key, "")).strip() if summary_key else f"{task} result"

    gate_input = GateInput(
        draft_text=draft_text or f"{task} result",
        task="reply",
        mode="json",
        risk_level=_derive_risk_level(draft_text or task),
        context_refs=[f"ai:{task}"],
        capabilities={"web_access": False, "file_access": False, "exec_access": False},
        generation_meta=generation_meta,
        commit_allowed=False,
        commit_allowed_by="none",
        source="assistant",
        subject="summary",
        facet="CANDIDATE",
    )
    gate_result = pre_output_gate(gate_input)
    payload = gate_result.model_dump(mode="json")

    if summary_key:
        if gate_result.outcome == EthicsOutcome.ADJUST and isinstance(gate_result.patch, dict):
            if gate_result.patch.get("kind") == "rewrite":
                candidate = str(gate_result.patch.get("content", "")).strip()
                if candidate:
                    contract_out[summary_key] = candidate
        elif gate_result.outcome == EthicsOutcome.PENDING:
            contract_out[summary_key] = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
        elif gate_result.outcome == EthicsOutcome.BLOCK:
            contract_out[summary_key] = "요청은 현재 정책상 즉시 처리할 수 없습니다."

    if payload.get("outcome") == EthicsOutcome.FIX.value:
        payload["outcome"] = EthicsOutcome.PENDING.value
        payload["reason_codes"] = ["INSUFFICIENT_EVIDENCE"]
        if summary_key:
            contract_out[summary_key] = "확인 불가: 필요한 입력을 먼저 확인해 주세요."
    return contract_out, payload


def _run_pre_commit_ethics(
    *,
    draft_text: str,
    context_refs: list[str],
    generation_meta: dict[str, Any],
    source: Literal["user", "assistant", "system"] = "system",
    subject: Literal["reply", "action", "rule", "summary", "decision"] = "summary",
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
    db,
    endpoint: str,
    task: str,
    draft_text: str,
    context_refs: list[str],
    generation_meta: dict[str, Any],
    provider_final: str = "local",
    fallback_applied: bool = False,
) -> dict[str, Any]:
    log_generation_line(generation_meta)
    commit_ethics = _run_pre_commit_ethics(
        draft_text=draft_text,
        context_refs=context_refs,
        generation_meta=generation_meta,
        source="system",
        subject="summary",
    )
    db.commit()
    write_lifecycle_event(
        "ETHICS_FIX_COMMITTED",
        {
            "project": "sophia",
            "endpoint": endpoint,
            "task": task,
            "provider_final": str(provider_final or "local"),
            "fallback_applied": bool(fallback_applied),
            "gate_reason": ",".join(commit_ethics.get("reason_codes", [])),
            "generation": generation_meta,
            "ethics": commit_ethics,
        },
        skill_id="ethics.gate",
    )
    return commit_ethics


@router.post("/ingest")
async def ai_ingest(payload: IngestRequest):
    db = _SessionLocal()
    try:
        input_text = str(payload.text or "")
        _ensure_non_empty_text(input_text)
        result = _ai_service.run(
            task="ingest",
            payload={
                "text": input_text,
                "source": payload.source,
                "context_tag_hint": payload.context_tag_hint or "",
            },
            provider=payload.provider,
            mode=payload.mode,
        )
        contract = dict(result["contract"])
        contract_redacted, redacted_fields_contract = redact_data(contract)

        meta = dict(result.get("meta", {}))
        gate = dict(result.get("gate", {}))
        generation_meta = _build_router_generation_meta(result_meta=meta)
        input_hash = sha256_text(input_text)
        input_len = len(input_text)
        quality_state = "FALLBACK" if bool(meta.get("fallback_applied", False)) else "NORMAL"
        safe_summary, quality_state = _sanitize_summary_for_storage(
            input_text=input_text,
            summary_text=str(contract.get("summary_120", "unknown")),
            input_hash=input_hash,
            input_len=input_len,
            source=payload.source,
            quality_state=quality_state,
        )

        candidate_id = f"ai:ingest:{input_hash.split(':', 1)[1][:16]}"
        mind_item = _upsert_mind_candidate(
            db,
            item_id=candidate_id,
            item_type="FOCUS",
            title="AI Ingest Candidate",
            summary=safe_summary,
            tags=_merge_unique(["ai", "ingest", "review_required"], [str(item) for item in contract_redacted.get("tags", [])]),
            source_event="AI_INGEST_PROCESSED",
            quality_state=quality_state,
            linked_bits=[str(contract_redacted.get("context_tag", "chat"))],
            risk_score=0.1,
            confidence=float(contract_redacted.get("confidence_model", 0.0) or 0.0),
        )

        event_payload = _build_ai_event_payload(
            endpoint="/ai/ingest",
            task="ingest",
            project=_safe_project(payload.project),
            schema=str(contract_redacted.get("schema", "")),
            input_hash=input_hash,
            input_len=input_len,
            provider_final=str(meta.get("provider_final", "")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
            gate_reason=str(gate.get("reason", "")),
            attempts_count=int(meta.get("attempts_count", 0)),
            quality_state=quality_state,
            mind_item_id=str(mind_item["id"]),
            extra={
                "source": payload.source,
                "context_tag": contract_redacted.get("context_tag", "chat"),
                "entities_count": len(contract_redacted.get("entities", [])),
                "tags_count": len(contract_redacted.get("tags", [])),
            },
        )
        event_payload_redacted, redacted_fields_event = redact_data(event_payload)
        all_redacted_fields = sorted(set([*redacted_fields_contract, *redacted_fields_event]))
        write_lifecycle_event("AI_INGEST_PROCESSED", event_payload_redacted, skill_id="ai.ingest")
        _commit_with_ethics(
            db=db,
            endpoint="/ai/ingest",
            task="ai.ingest",
            draft_text=json.dumps(event_payload_redacted, ensure_ascii=False, sort_keys=True),
            context_refs=[str(mind_item["id"]), "/ai/ingest"],
            generation_meta=generation_meta,
            provider_final=str(meta.get("provider_final", "local")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
        )
        return _make_response(
            task="ingest",
            result=result,
            contract_redacted=contract_redacted,
            redacted_fields=all_redacted_fields,
            mind_item=mind_item,
            quality_state=quality_state,
            generation_meta=generation_meta,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"code": "AI_BAD_REQUEST", "message": str(exc)})
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/transcript/process")
async def ai_transcript_process(payload: TranscriptProcessRequest):
    db = _SessionLocal()
    try:
        input_text = str(payload.text or "")
        _ensure_non_empty_text(input_text)
        result = _ai_service.run(
            task="transcript",
            payload={"text": input_text, "source": payload.source},
            provider=payload.provider,
            mode=payload.mode,
        )
        contract = dict(result["contract"])
        contract_redacted, redacted_fields_contract = redact_data(contract)
        meta = dict(result.get("meta", {}))
        gate = dict(result.get("gate", {}))
        generation_meta = _build_router_generation_meta(result_meta=meta)
        input_hash = sha256_text(input_text)
        input_len = len(input_text)
        quality_state = "FALLBACK" if bool(meta.get("fallback_applied", False)) else "NORMAL"
        safe_summary, quality_state = _sanitize_summary_for_storage(
            input_text=input_text,
            summary_text=str(contract.get("summary", "unknown")),
            input_hash=input_hash,
            input_len=input_len,
            source=payload.source,
            quality_state=quality_state,
        )
        candidate_id = f"ai:transcript:{input_hash.split(':', 1)[1][:16]}"
        mind_item = _upsert_mind_candidate(
            db,
            item_id=candidate_id,
            item_type="TASK",
            title="Transcript Candidate",
            summary=safe_summary,
            tags=["ai", "transcript", "review_required"],
            source_event="AI_TRANSCRIPT_PROCESSED",
            quality_state=quality_state,
            linked_bits=["transcript"],
            risk_score=0.3 if contract_redacted.get("open_questions") else 0.1,
            confidence=0.62,
        )

        event_payload = _build_ai_event_payload(
            endpoint="/ai/transcript/process",
            task="transcript",
            project=_safe_project(payload.project),
            schema=str(contract_redacted.get("schema", "")),
            input_hash=input_hash,
            input_len=input_len,
            provider_final=str(meta.get("provider_final", "")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
            gate_reason=str(gate.get("reason", "")),
            attempts_count=int(meta.get("attempts_count", 0)),
            quality_state=quality_state,
            mind_item_id=str(mind_item["id"]),
            extra={
                "action_items_count": len(contract_redacted.get("action_items", [])),
                "decisions_count": len(contract_redacted.get("decisions", [])),
                "open_questions_count": len(contract_redacted.get("open_questions", [])),
            },
        )
        event_payload_redacted, redacted_fields_event = redact_data(event_payload)
        all_redacted_fields = sorted(set([*redacted_fields_contract, *redacted_fields_event]))
        write_lifecycle_event("AI_TRANSCRIPT_PROCESSED", event_payload_redacted, skill_id="ai.transcript")
        _commit_with_ethics(
            db=db,
            endpoint="/ai/transcript/process",
            task="ai.transcript",
            draft_text=json.dumps(event_payload_redacted, ensure_ascii=False, sort_keys=True),
            context_refs=[str(mind_item["id"]), "/ai/transcript/process"],
            generation_meta=generation_meta,
            provider_final=str(meta.get("provider_final", "local")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
        )
        return _make_response(
            task="transcript",
            result=result,
            contract_redacted=contract_redacted,
            redacted_fields=all_redacted_fields,
            mind_item=mind_item,
            quality_state=quality_state,
            generation_meta=generation_meta,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"code": "AI_BAD_REQUEST", "message": str(exc)})
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/rules/candidates")
async def ai_rules_candidates(payload: RulesCandidatesRequest):
    db = _SessionLocal()
    try:
        joined_text = "\n".join([item for item in payload.text_bundle if isinstance(item, str)])
        _ensure_non_empty_text(joined_text)
        result = _ai_service.run(
            task="rules",
            payload={"text": joined_text, "refs": payload.refs},
            provider=payload.provider,
            mode=payload.mode,
        )
        contract = dict(result["contract"])
        contract_redacted, redacted_fields_contract = redact_data(contract)
        meta = dict(result.get("meta", {}))
        gate = dict(result.get("gate", {}))
        generation_meta = _build_router_generation_meta(result_meta=meta)
        input_hash = sha256_text(joined_text)
        input_len = len(joined_text)
        quality_state = "FALLBACK" if bool(meta.get("fallback_applied", False)) else "NORMAL"
        safe_summary, quality_state = _sanitize_summary_for_storage(
            input_text=joined_text,
            summary_text=f"규칙 후보 {len(contract_redacted.get('candidates', []))}건 검토 필요",
            input_hash=input_hash,
            input_len=input_len,
            source="rules_bundle",
            quality_state=quality_state,
        )
        candidate_id = f"ai:rules:{input_hash.split(':', 1)[1][:16]}"
        mind_item = _upsert_mind_candidate(
            db,
            item_id=candidate_id,
            item_type="FOCUS",
            title="Rule Candidate Review",
            summary=safe_summary,
            tags=["ai", "rules", "review_required"],
            source_event="AI_RULE_CANDIDATES_PROCESSED",
            quality_state=quality_state,
            linked_bits=["rules"],
            risk_score=0.2,
            confidence=0.5,
        )

        event_payload = _build_ai_event_payload(
            endpoint="/ai/rules/candidates",
            task="rules",
            project=_safe_project(payload.project),
            schema=str(contract_redacted.get("schema", "")),
            input_hash=input_hash,
            input_len=input_len,
            provider_final=str(meta.get("provider_final", "")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
            gate_reason=str(gate.get("reason", "")),
            attempts_count=int(meta.get("attempts_count", 0)),
            quality_state=quality_state,
            mind_item_id=str(mind_item["id"]),
            extra={
                "candidate_count": len(contract_redacted.get("candidates", [])),
                "refs_count": len(payload.refs),
            },
        )
        event_payload_redacted, redacted_fields_event = redact_data(event_payload)
        all_redacted_fields = sorted(set([*redacted_fields_contract, *redacted_fields_event]))
        write_lifecycle_event("AI_RULE_CANDIDATES_PROCESSED", event_payload_redacted, skill_id="ai.rules")
        _commit_with_ethics(
            db=db,
            endpoint="/ai/rules/candidates",
            task="ai.rules",
            draft_text=json.dumps(event_payload_redacted, ensure_ascii=False, sort_keys=True),
            context_refs=[str(mind_item["id"]), "/ai/rules/candidates"],
            generation_meta=generation_meta,
            provider_final=str(meta.get("provider_final", "local")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
        )
        return _make_response(
            task="rules",
            result=result,
            contract_redacted=contract_redacted,
            redacted_fields=all_redacted_fields,
            mind_item=mind_item,
            quality_state=quality_state,
            generation_meta=generation_meta,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"code": "AI_BAD_REQUEST", "message": str(exc)})
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()


@router.post("/diff/summarize")
async def ai_diff_summarize(payload: DiffSummarizeRequest):
    db = _SessionLocal()
    try:
        before_text = str(payload.before_text or "")
        after_text = str(payload.after_text or "")
        if not before_text.strip() and not after_text.strip():
            raise HTTPException(
                status_code=400,
                detail={"code": "AI_EMPTY_INPUT", "message": "text is empty"},
            )
        result = _ai_service.run(
            task="diff",
            payload={
                "before_text": before_text,
                "after_text": after_text,
                "doc_path": payload.doc_path,
            },
            provider=payload.provider,
            mode=payload.mode,
        )
        contract = dict(result["contract"])
        contract_redacted, redacted_fields_contract = redact_data(contract)
        meta = dict(result.get("meta", {}))
        gate = dict(result.get("gate", {}))
        generation_meta = _build_router_generation_meta(result_meta=meta)
        input_hash = sha256_text(json.dumps({"before": before_text, "after": after_text}, ensure_ascii=False))
        input_len = len(before_text) + len(after_text)
        quality_state = "FALLBACK" if bool(meta.get("fallback_applied", False)) else "NORMAL"
        safe_summary, quality_state = _sanitize_summary_for_storage(
            input_text=f"{before_text}\n{after_text}",
            summary_text=str(contract.get("diff_summary", "unknown")),
            input_hash=input_hash,
            input_len=input_len,
            source=payload.doc_path or "diff",
            quality_state=quality_state,
        )
        candidate_id = f"ai:diff:{input_hash.split(':', 1)[1][:16]}"
        mind_item = _upsert_mind_candidate(
            db,
            item_id=candidate_id,
            item_type="ALERT",
            title="Diff Review Required",
            summary=safe_summary,
            tags=["ai", "diff", "review_required"],
            source_event="AI_DIFF_SUMMARIZED",
            quality_state=quality_state,
            linked_bits=[payload.doc_path or "doc"],
            risk_score=0.4 if contract_redacted.get("clarify") else 0.2,
            confidence=0.58,
        )

        event_payload = _build_ai_event_payload(
            endpoint="/ai/diff/summarize",
            task="diff",
            project=_safe_project(payload.project),
            schema=str(contract_redacted.get("schema", "")),
            input_hash=input_hash,
            input_len=input_len,
            provider_final=str(meta.get("provider_final", "")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
            gate_reason=str(gate.get("reason", "")),
            attempts_count=int(meta.get("attempts_count", 0)),
            quality_state=quality_state,
            mind_item_id=str(mind_item["id"]),
            extra={
                "doc_path": payload.doc_path,
                "affected_modules_count": len(contract_redacted.get("affected_modules", [])),
                "clarify_count": len(contract_redacted.get("clarify", [])),
            },
        )
        event_payload_redacted, redacted_fields_event = redact_data(event_payload)
        all_redacted_fields = sorted(set([*redacted_fields_contract, *redacted_fields_event]))
        write_lifecycle_event("AI_DIFF_SUMMARIZED", event_payload_redacted, skill_id="ai.diff")
        _commit_with_ethics(
            db=db,
            endpoint="/ai/diff/summarize",
            task="ai.diff",
            draft_text=json.dumps(event_payload_redacted, ensure_ascii=False, sort_keys=True),
            context_refs=[str(mind_item["id"]), "/ai/diff/summarize"],
            generation_meta=generation_meta,
            provider_final=str(meta.get("provider_final", "local")),
            fallback_applied=bool(meta.get("fallback_applied", False)),
        )
        return _make_response(
            task="diff",
            result=result,
            contract_redacted=contract_redacted,
            redacted_fields=all_redacted_fields,
            mind_item=mind_item,
            quality_state=quality_state,
            generation_meta=generation_meta,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"code": "AI_BAD_REQUEST", "message": str(exc)})
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        db.close()
