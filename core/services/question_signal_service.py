from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from core.memory.schema import QuestionPool


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalize_evidence(
    *,
    snippet: str | None,
    source: str | None,
    timestamp: str | None = None,
) -> dict[str, str]:
    return {
        "snippet": (snippet or "").strip()[:400],
        "source": (source or "").strip()[:200],
        "timestamp": (timestamp or _utc_now().isoformat().replace("+00:00", "Z")).strip(),
    }


def _dedupe_evidence(items: list[dict[str, str]], max_items: int = 50) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for item in reversed(items):
        key = f"{item.get('snippet','')}|{item.get('source','')}|{item.get('timestamp','')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max_items:
            break
    result.reverse()
    return result


def upsert_question_signal(
    *,
    session,
    cluster_id: str,
    description: str,
    risk_score: float,
    snippet: str | None = None,
    source: str | None = None,
    evidence_timestamp: str | None = None,
    linked_node: str | None = None,
    write_event: Callable[[str, dict[str, Any]], None] | None = None,
    on_question_ready: Callable[[Any, QuestionPool], None] | None = None,
    enqueue_if_ready: Callable[[Any, QuestionPool], Any | None] | None = None,
) -> tuple[QuestionPool, Any | None]:
    row = session.query(QuestionPool).filter(QuestionPool.cluster_id == cluster_id).one_or_none()
    now = _utc_now()
    if row is None:
        row = QuestionPool(
            cluster_id=cluster_id,
            description=description,
            hit_count=0,
            risk_score=0.0,
            evidence=[],
            linked_nodes=[],
            status="collecting",
            last_triggered_at=now,
            asked_count=0,
        )
        session.add(row)
        session.flush()

    if row.status == "resolved":
        row.hit_count = 0
        row.risk_score = 0.0
        row.evidence = []
        row.status = "collecting"

    row.hit_count = int(row.hit_count or 0) + 1
    row.risk_score = max(float(row.risk_score or 0.0), float(risk_score))
    row.description = description
    row.last_triggered_at = now

    evidence = list(row.evidence or [])
    evidence.append(
        _normalize_evidence(
            snippet=snippet,
            source=source,
            timestamp=evidence_timestamp,
        )
    )
    row.evidence = _dedupe_evidence(evidence)

    linked_nodes = list(row.linked_nodes or [])
    if linked_node and linked_node not in linked_nodes:
        linked_nodes.append(linked_node)
    row.linked_nodes = linked_nodes

    threshold_met = row.hit_count >= 3 or float(row.risk_score) >= 0.8
    previous_status = str(row.status or "collecting")
    if threshold_met and previous_status == "collecting":
        row.status = "ready_to_ask"
        if write_event is not None:
            write_event(
                "QUESTION_READY",
                {
                    "cluster_id": row.cluster_id,
                    "hit_count": int(row.hit_count or 0),
                    "risk_score": float(row.risk_score or 0.0),
                },
            )
        if on_question_ready is not None:
            on_question_ready(session, row)
    elif not threshold_met and previous_status not in {"pending", "acknowledged", "resolved"}:
        row.status = "collecting"

    session.add(row)
    session.flush()

    if write_event is not None:
        write_event(
            "QUESTION_SIGNAL",
            {
                "cluster_id": row.cluster_id,
                "hit_count": int(row.hit_count or 0),
                "risk_score": float(row.risk_score or 0.0),
                "status": row.status,
            },
        )

    pending = enqueue_if_ready(session, row) if enqueue_if_ready is not None else None
    return row, pending
