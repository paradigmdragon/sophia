from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.memory.schema import MindLearningRollup, MindLearningRollupTrace

TRACKED_LEARNING_EVENTS = (
    "UNCONSCIOUS_HIT",
    "UNCONSCIOUS_PATTERN_SEEN",
    "TERM_MAPPING",
    "TOPIC_SEEN",
    "USER_PREFERENCE",
)

ROLLUP_TOTAL = "TOTAL"
ROLLUP_DAILY = "DAILY"
ROLLUP_WINDOW_24H = "WINDOW_24H"
ROLLUP_TOP_PATTERNS = "TOP_PATTERNS"
ROLLUP_EVENT_DAILY = "EVENT_DAILY"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


def _normalize_pattern_id(event_type: str, payload: dict[str, Any] | None) -> str | None:
    if event_type not in {"UNCONSCIOUS_HIT", "UNCONSCIOUS_PATTERN_SEEN"}:
        return None
    value = str((payload or {}).get("pattern_id", "")).strip().upper()
    return value or None


def _ensure_rollup_row(
    session,
    *,
    rollup_type: str,
    bucket_key: str,
    now: datetime,
) -> MindLearningRollup:
    row = (
        session.query(MindLearningRollup)
        .filter(
            MindLearningRollup.rollup_type == rollup_type,
            MindLearningRollup.bucket_key == bucket_key,
        )
        .one_or_none()
    )
    if row is None:
        row = MindLearningRollup(
            rollup_type=rollup_type,
            bucket_key=bucket_key,
            payload={},
            source_event_count=0,
            computed_at=now,
        )
    if not isinstance(row.payload, dict):
        row.payload = {}
    return row


def _increment_counter(counter: dict[str, int], key: str, delta: int = 1) -> None:
    counter[key] = int(counter.get(key, 0) or 0) + int(delta)


def _growth_stage(total_tracked_events: int) -> str:
    if total_tracked_events < 10:
        return "SEED"
    if total_tracked_events < 40:
        return "SPROUT"
    return "GROWING"


def _round_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator / denominator)


def _hour_bucket_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H")


def _parse_hour_bucket(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H").replace(tzinfo=UTC)
    except ValueError:
        return None


def _prune_hour_buckets(hour_buckets: dict[str, dict[str, int]], now: datetime) -> dict[str, dict[str, int]]:
    cutoff = now - timedelta(hours=24)
    out: dict[str, dict[str, int]] = {}
    for key, bucket in hour_buckets.items():
        bucket_dt = _parse_hour_bucket(key)
        if bucket_dt is None or bucket_dt < cutoff:
            continue
        cleaned: dict[str, int] = {}
        if isinstance(bucket, dict):
            for event_name, count in bucket.items():
                cleaned[str(event_name)] = int(count or 0)
        out[key] = cleaned
    return out


def _build_source_events_top(source_event_counts: dict[str, int], *, limit: int = 10) -> list[dict[str, Any]]:
    return [
        {"event_type": key, "count": value}
        for key, value in sorted(source_event_counts.items(), key=lambda row: (-row[1], row[0]))[:limit]
    ]


def update_learning_rollup_on_event(
    session,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
    trace_id: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    if event_type not in TRACKED_LEARNING_EVENTS:
        return {"updated": False, "reason": "not_tracked"}

    now = occurred_at or _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    else:
        now = now.astimezone(UTC)

    day_key = now.date().isoformat()
    trace = str(trace_id or (payload or {}).get("trace_id") or "").strip()
    if trace:
        exists = (
            session.query(MindLearningRollupTrace.id)
            .filter(
                MindLearningRollupTrace.event_date == day_key,
                MindLearningRollupTrace.event_type == event_type,
                MindLearningRollupTrace.trace_id == trace,
            )
            .one_or_none()
        )
        if exists is not None:
            return {"updated": False, "reason": "dedup_trace"}
        session.add(
            MindLearningRollupTrace(
                event_date=day_key,
                event_type=event_type,
                trace_id=trace,
                created_at=now,
            )
        )
        session.flush()

    pattern_id = _normalize_pattern_id(event_type, payload)
    pattern_bucket = pattern_id or "_"
    event_daily_bucket = f"{day_key}:{event_type}:{pattern_bucket}"

    event_daily = _ensure_rollup_row(
        session,
        rollup_type=ROLLUP_EVENT_DAILY,
        bucket_key=event_daily_bucket,
        now=now,
    )
    event_daily_payload = dict(event_daily.payload or {})
    event_daily_count = int(event_daily_payload.get("count", 0) or 0) + 1
    event_daily_payload.update(
        {
            "date": day_key,
            "event_type": event_type,
            "pattern_id": pattern_id,
            "count": event_daily_count,
            "last_at": _to_iso(now),
        }
    )
    event_daily.payload = event_daily_payload
    event_daily.source_event_count = event_daily_count
    event_daily.computed_at = now
    session.add(event_daily)

    total_row = _ensure_rollup_row(session, rollup_type=ROLLUP_TOTAL, bucket_key="all", now=now)
    total_payload = dict(total_row.payload or {})
    tracked_events = {
        name: int(value or 0)
        for name, value in (total_payload.get("tracked_events", {}) or {}).items()
    }
    _increment_counter(tracked_events, event_type, 1)
    total_count = int(total_payload.get("total_tracked_events", 0) or 0) + 1
    source_event_counts = {
        name: int(value or 0)
        for name, value in (total_payload.get("source_event_counts", {}) or {}).items()
    }
    _increment_counter(source_event_counts, event_type, 1)
    unconscious_hits = int(tracked_events.get("UNCONSCIOUS_HIT", 0) or 0)
    preference_hits = int(tracked_events.get("USER_PREFERENCE", 0) or 0)
    topic_hits = int(tracked_events.get("TOPIC_SEEN", 0) or 0)
    total_payload.update(
        {
            "tracked_events": tracked_events,
            "total_tracked_events": total_count,
            "nonzero_event_kinds": int(sum(1 for value in tracked_events.values() if int(value or 0) > 0)),
            "last_event_at": _to_iso(now),
            "growth_stage": _growth_stage(total_count),
            "unconscious_ratio": _round_ratio(unconscious_hits, total_count),
            "preference_stability": _round_ratio(preference_hits, total_count),
            "topic_density": _round_ratio(topic_hits, total_count),
            "source_event_counts": source_event_counts,
            "source_events_top": _build_source_events_top(source_event_counts),
        }
    )
    total_row.payload = total_payload
    total_row.source_event_count = total_count
    total_row.computed_at = now
    session.add(total_row)

    daily_row = _ensure_rollup_row(session, rollup_type=ROLLUP_DAILY, bucket_key=day_key, now=now)
    daily_payload = dict(daily_row.payload or {})
    tracked_day = {
        name: int(value or 0)
        for name, value in (daily_payload.get("tracked_events_day", {}) or {}).items()
    }
    _increment_counter(tracked_day, event_type, 1)
    daily_payload.update({"tracked_events_day": tracked_day})
    daily_row.payload = daily_payload
    daily_row.source_event_count = int(daily_row.source_event_count or 0) + 1
    daily_row.computed_at = now
    session.add(daily_row)

    window_row = _ensure_rollup_row(session, rollup_type=ROLLUP_WINDOW_24H, bucket_key="rolling", now=now)
    window_payload = dict(window_row.payload or {})
    hour_buckets_raw = window_payload.get("hour_buckets", {})
    hour_buckets: dict[str, dict[str, int]] = {}
    if isinstance(hour_buckets_raw, dict):
        for hour_key, per_event in hour_buckets_raw.items():
            if not isinstance(per_event, dict):
                continue
            hour_buckets[str(hour_key)] = {str(k): int(v or 0) for k, v in per_event.items()}
    hour_buckets = _prune_hour_buckets(hour_buckets, now)
    current_hour = _hour_bucket_key(now)
    hour_bucket = hour_buckets.get(current_hour, {})
    _increment_counter(hour_bucket, event_type, 1)
    hour_buckets[current_hour] = hour_bucket

    tracked_24h = {event: 0 for event in TRACKED_LEARNING_EVENTS}
    for bucket in hour_buckets.values():
        for name, value in bucket.items():
            if name in tracked_24h:
                tracked_24h[name] = int(tracked_24h[name]) + int(value or 0)
    window_payload.update(
        {
            "hour_buckets": hour_buckets,
            "tracked_events_24h": tracked_24h,
        }
    )
    window_row.payload = window_payload
    window_row.source_event_count = int(sum(tracked_24h.values()))
    window_row.computed_at = now
    session.add(window_row)

    top_row = _ensure_rollup_row(session, rollup_type=ROLLUP_TOP_PATTERNS, bucket_key="rolling", now=now)
    top_payload = dict(top_row.payload or {})
    pattern_counts = {
        str(k): int(v or 0) for k, v in (top_payload.get("pattern_counts", {}) or {}).items()
    }
    if pattern_id:
        _increment_counter(pattern_counts, pattern_id, 1)
    top_patterns = [
        {"pattern_id": key, "count": value}
        for key, value in sorted(pattern_counts.items(), key=lambda row: (-row[1], row[0]))[:5]
    ]
    top_payload.update(
        {
            "pattern_counts": pattern_counts,
            "top_unconscious_patterns": top_patterns,
        }
    )
    top_row.payload = top_payload
    top_row.source_event_count = int(sum(pattern_counts.values()))
    top_row.computed_at = now
    session.add(top_row)

    session.flush()
    return {
        "updated": True,
        "event_type": event_type,
        "pattern_id": pattern_id,
        "day": day_key,
    }
