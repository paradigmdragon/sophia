from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.forest.layout import ensure_project_layout, get_project_root, write_json
from core.forest.sone_reason_codes import (
    REASON_DEPENDENCY_UNSPECIFIED,
    REASON_REQUIREMENT_CONFLICT,
    REASON_SCOPE_MISSING,
    normalize_signal_reason,
    slot_reason_codes,
)


def _to_iso(value: datetime | None = None) -> str:
    dt = value or datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def sanitize_doc_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return f"doc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.md"
    raw = raw.replace("\\", "/").split("/")[-1]
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-")
    if not safe:
        safe = f"doc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
    if not safe.endswith(".md"):
        safe += ".md"
    return safe


def extract_first_heading(content: str) -> str:
    for line in content.splitlines():
        text = line.strip()
        if text.startswith("#"):
            return text.lstrip("#").strip()
        if text:
            return text[:120]
    return ""


def extract_constraints(content: str) -> list[str]:
    rows: list[str] = []
    for line in content.splitlines():
        text = line.strip()
        if not text:
            continue
        lowered = text.lower()
        if any(token in lowered for token in ["must", "constraint", "제약", "금지", "필수", "필요"]):
            rows.append(text[:200])
        if len(rows) >= 8:
            break
    return rows


def extract_impacts(content: str) -> list[str]:
    pattern = re.compile(r"\b[a-z0-9]+(?:[-_][a-z0-9]+)*(?:-module|-manager|-service)\b", re.IGNORECASE)
    impacts: list[str] = []
    seen: set[str] = set()
    for match in pattern.findall(content):
        token = match.lower()
        if token in seen:
            continue
        seen.add(token)
        impacts.append(token)
        if len(impacts) >= 10:
            break
    if "session-manager" in content.lower() and "session-manager" not in seen:
        impacts.append("session-manager")
    return impacts


def infer_scope(scope: str | None, content: str) -> str:
    if isinstance(scope, str) and scope.strip():
        return scope.strip()
    lowered = content.lower()
    if "mobile" in lowered or "모바일" in lowered:
        return "mobile only"
    if "web" in lowered:
        return "web only"
    if "backend" in lowered or "server" in lowered:
        return "backend"
    return ""


def has_success_condition(content: str) -> bool:
    lowered = content.lower()
    return any(
        token in lowered
        for token in [
            "success condition",
            "acceptance",
            "완료 기준",
            "성공 조건",
            "done criteria",
        ]
    )


def build_sone_slot(
    *,
    target: str,
    change: str,
    scope: str,
    content: str,
    evidence: str,
) -> dict[str, Any]:
    constraints = extract_constraints(content)
    impact = extract_impacts(content)
    success = has_success_condition(content)
    status = "ok"
    if not success:
        status = "missing_success_condition"
    elif not scope:
        status = "missing_scope"

    return {
        "target": target or "unknown-target",
        "change": change or extract_first_heading(content) or "변경 사항 확인 필요",
        "scope": scope or "",
        "success_condition": "defined" if success else None,
        "constraints": constraints,
        "impact": impact,
        "evidence": evidence,
        "status": status,
        "reason_codes": slot_reason_codes(status),
    }


def signals_from_slot(slot: dict[str, Any], content: str) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    lowered = content.lower()
    if not str(slot.get("scope", "")).strip():
        signals.append(
            normalize_signal_reason(
                {
                    "cluster_id": "scope_ambiguity",
                    "description": "범위 불명확",
                    "risk_score": 0.82,
                    "reason_code": REASON_SCOPE_MISSING,
                    "evidence": "slot.scope is empty",
                }
            )
        )
    if slot.get("impact") and "dependency" not in lowered and "의존" not in lowered:
        signals.append(
            normalize_signal_reason(
                {
                    "cluster_id": "dependency_missing",
                    "description": "의존 관계 불명확",
                    "risk_score": 0.76,
                    "reason_code": REASON_DEPENDENCY_UNSPECIFIED,
                    "evidence": f"impact={','.join(slot.get('impact', [])[:3])}",
                }
            )
        )
    if any(token in lowered for token in ["conflict", "충돌", "상충", "모순"]):
        signals.append(
            normalize_signal_reason(
                {
                    "cluster_id": "requirement_conflict",
                    "description": "요구사항 충돌 가능성",
                    "risk_score": 0.86,
                    "reason_code": REASON_REQUIREMENT_CONFLICT,
                    "evidence": "conflict keyword detected",
                }
            )
        )
    return signals


def analyze_to_forest(
    *,
    project_name: str,
    doc_name: str,
    content: str,
    target: str,
    change: str,
    scope: str | None = None,
    write_doc: bool = True,
) -> dict[str, Any]:
    ensure_project_layout(project_name)
    root = get_project_root(project_name)
    docs_dir = root / "docs"
    analysis_dir = root / "analysis"

    safe_doc = sanitize_doc_name(doc_name)
    if write_doc:
        (docs_dir / safe_doc).write_text(content, encoding="utf-8")

    scoped = infer_scope(scope, content)
    slot = build_sone_slot(target=target, change=change, scope=scoped, content=content, evidence=safe_doc)
    signals = signals_from_slot(slot, content)

    dependency_graph = {
        "nodes": [slot["target"], *slot.get("impact", [])],
        "edges": [{"from": slot["target"], "to": dep} for dep in slot.get("impact", [])],
    }
    risk_snapshot = {
        "generated_at": _to_iso(),
        "clusters": signals,
        "threshold": 0.8,
    }
    last_delta = {
        "generated_at": _to_iso(),
        "source_doc": safe_doc,
        "slots": [slot],
    }

    last_delta_path = analysis_dir / "last_delta.sone.json"
    dependency_path = analysis_dir / "dependency_graph.json"
    risk_path = analysis_dir / "risk_snapshot.json"
    write_json(last_delta_path, last_delta)
    write_json(dependency_path, dependency_graph)
    write_json(risk_path, risk_snapshot)

    findings: list[str] = []
    if slot.get("success_condition") is None:
        findings.append("성공 조건 미정")
    if not slot.get("scope"):
        findings.append("범위 불명확")
    if slot.get("impact"):
        findings.append(f"영향 범위: {', '.join(slot['impact'])}")
    if signals:
        findings.append(f"질문 후보 {len(signals)}개 생성")

    return {
        "project": project_name,
        "doc_name": safe_doc,
        "slot": slot,
        "signals": signals,
        "human_findings": findings,
        "paths": {
            "last_delta": str(last_delta_path),
            "dependency_graph": str(dependency_path),
            "risk_snapshot": str(risk_path),
            "doc_path": str(docs_dir / safe_doc),
        },
    }
