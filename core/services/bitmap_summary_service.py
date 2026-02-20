from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import inspect as sa_inspect, text


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _shorten_text(value: str, *, max_chars: int = 180) -> str:
    return " ".join((value or "").split())[:max_chars]


def _parse_iso_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _is_recent(value: Any, *, days: int) -> bool:
    dt = _parse_iso_dt(value)
    if dt is None:
        return False
    return (_utc_now() - dt) <= timedelta(days=days)


def _payload_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text_value = raw.strip()
        if not text_value:
            return {}
        try:
            parsed = json.loads(text_value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def build_bitmap_summary(session, *, days: int = 7, limit: int = 5) -> dict[str, Any]:
    bind = session.get_bind()
    if bind is None:
        return {"candidates": [], "anchors": [], "invalid_recent": [], "metrics": {}}

    try:
        inspector = sa_inspect(bind)
    except Exception:
        return {
            "candidates": [],
            "anchors": [],
            "invalid_recent": [],
            "metrics": {},
            "lifecycle": {
                "window_days": int(days),
                "candidate_status_counts": {},
                "event_counts": {},
                "invalid_reason_counts": {},
                "adoption_rate": 0.0,
                "pending_count": 0,
                "recent_transitions": [],
            },
        }

    candidates: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    invalid_recent: list[dict[str, Any]] = []
    candidate_status_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    invalid_reason_counts: dict[str, int] = {}
    recent_transitions: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "candidate_count_7d": 0,
        "anchor_count_7d": 0,
        "rejected_count_7d": 0,
        "invalid_count_7d": 0,
        "conflict_mark_count_7d": 0,
        "duplicate_combined_groups": 0,
        "duplicate_backbone_rows": 0,
        "status_counts_7d": {},
    }

    try:
        if inspector.has_table("candidates"):
            rows = session.execute(
                text(
                    """
                    SELECT candidate_id, episode_id, note_thin, confidence, proposed_at, status
                    FROM candidates
                    ORDER BY proposed_at DESC
                    LIMIT 500
                    """
                )
            ).fetchall()
            for row in rows:
                proposed_at = row[4]
                if proposed_at is not None and not _is_recent(proposed_at, days=days):
                    continue
                status = str(row[5] or "").upper()
                candidate_status_counts[status] = int(candidate_status_counts.get(status, 0)) + 1
                metrics["candidate_count_7d"] = int(metrics["candidate_count_7d"]) + 1
                status_counts = metrics["status_counts_7d"]
                status_counts[status] = int(status_counts.get(status, 0)) + 1
                if status == "REJECTED":
                    metrics["rejected_count_7d"] = int(metrics["rejected_count_7d"]) + 1
                parsed_proposed_at = _parse_iso_dt(proposed_at)
                candidates.append(
                    {
                        "id": str(row[0]),
                        "episode_id": str(row[1] or ""),
                        "note": _shorten_text(str(row[2] or ""), max_chars=120),
                        "confidence": int(row[3] or 0),
                        "proposed_at": _to_iso(parsed_proposed_at) if parsed_proposed_at else "",
                        "status": status or "UNKNOWN",
                    }
                )
                if len(candidates) >= limit:
                    break

        if inspector.has_table("backbones"):
            rows = session.execute(
                text(
                    """
                    SELECT backbone_id, combined_bits, role, adopted_at
                    FROM backbones
                    ORDER BY adopted_at DESC
                    LIMIT 50
                    """
                )
            ).fetchall()
            for row in rows:
                adopted_at = row[3]
                if adopted_at is not None and not _is_recent(adopted_at, days=days):
                    continue
                metrics["anchor_count_7d"] = int(metrics["anchor_count_7d"]) + 1
                parsed_adopted_at = _parse_iso_dt(adopted_at)
                anchors.append(
                    {
                        "id": str(row[0]),
                        "bits": int(row[1] or 0),
                        "role": str(row[2] or ""),
                        "adopted_at": _to_iso(parsed_adopted_at) if parsed_adopted_at else "",
                    }
                )
                if len(anchors) >= limit:
                    break

            duplicate_rows = session.execute(
                text(
                    """
                    SELECT combined_bits, COUNT(*) AS cnt
                    FROM backbones
                    GROUP BY combined_bits
                    HAVING COUNT(*) > 1
                    """
                )
            ).fetchall()
            metrics["duplicate_combined_groups"] = int(len(duplicate_rows))
            duplicate_total = 0
            for group in duplicate_rows:
                duplicate_total += max(0, int(group[1] or 0) - 1)
            metrics["duplicate_backbone_rows"] = int(duplicate_total)

        if inspector.has_table("events"):
            invalid_rows = session.execute(
                text(
                    """
                    SELECT type, payload, at
                    FROM events
                    WHERE type = 'BITMAP_INVALID'
                    ORDER BY at DESC
                    LIMIT 100
                    """
                )
            ).fetchall()
            for row in invalid_rows:
                created_at = row[2]
                if created_at is not None and not _is_recent(created_at, days=days):
                    continue
                metrics["invalid_count_7d"] = int(metrics["invalid_count_7d"]) + 1
                payload = _payload_dict(row[1])
                reason = str(payload.get("reason", "")).strip().upper() or "UNKNOWN"
                invalid_reason_counts[reason] = int(invalid_reason_counts.get(reason, 0)) + 1
                bits_raw = payload.get("bits_raw")
                bits_text = str(bits_raw)
                if isinstance(bits_raw, int):
                    bits_text = f"0x{int(bits_raw) & 0xFFFF:04X}"
                invalid_recent.append(
                    {
                        "stage": str(payload.get("stage", "")),
                        "reason": reason,
                        "bits": bits_text,
                        "at": _to_iso(_parse_iso_dt(created_at)) if _parse_iso_dt(created_at) else "",
                    }
                )
                if len(invalid_recent) >= limit:
                    break

            conflict_rows = session.execute(
                text(
                    """
                    SELECT type, payload, at
                    FROM events
                    WHERE type = 'CONFLICT_MARK'
                    ORDER BY at DESC
                    LIMIT 200
                    """
                )
            ).fetchall()
            for row in conflict_rows:
                created_at = row[2]
                if created_at is not None and not _is_recent(created_at, days=days):
                    continue
                metrics["conflict_mark_count_7d"] = int(metrics["conflict_mark_count_7d"]) + 1

            transition_rows = session.execute(
                text(
                    """
                    SELECT type, payload, at
                    FROM events
                    WHERE type IN ('PROPOSE', 'ADOPT', 'REJECT', 'BITMAP_INVALID', 'CONFLICT_MARK')
                    ORDER BY at DESC
                    LIMIT 200
                    """
                )
            ).fetchall()
            for row in transition_rows:
                created_at = row[2]
                if created_at is not None and not _is_recent(created_at, days=days):
                    continue
                event_type = str(row[0] or "").upper()
                event_counts[event_type] = int(event_counts.get(event_type, 0)) + 1
                payload = _payload_dict(row[1])
                candidate_id = str(payload.get("candidate_id", "")).strip()
                reason = str(payload.get("reason", "")).strip().upper()
                recent_transitions.append(
                    {
                        "event_type": event_type,
                        "at": _to_iso(_parse_iso_dt(created_at)) if _parse_iso_dt(created_at) else "",
                        "candidate_id": candidate_id,
                        "reason": reason,
                    }
                )
                if len(recent_transitions) >= limit * 4:
                    break
    except Exception:
        return {"candidates": [], "anchors": [], "invalid_recent": [], "metrics": {}}

    adopted = int(candidate_status_counts.get("ADOPTED", 0))
    rejected = int(candidate_status_counts.get("REJECTED", 0))
    pending = int(candidate_status_counts.get("PENDING", 0))
    resolved_total = adopted + rejected
    adoption_rate = float(adopted / resolved_total) if resolved_total > 0 else 0.0

    return {
        "candidates": candidates,
        "anchors": anchors,
        "invalid_recent": invalid_recent,
        "metrics": metrics,
        "lifecycle": {
            "window_days": int(days),
            "candidate_status_counts": candidate_status_counts,
            "event_counts": event_counts,
            "invalid_reason_counts": invalid_reason_counts,
            "adoption_rate": adoption_rate,
            "pending_count": pending,
            "recent_transitions": recent_transitions,
        },
    }
