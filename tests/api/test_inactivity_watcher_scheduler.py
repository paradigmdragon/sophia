from __future__ import annotations

from datetime import UTC, datetime, timedelta

from api import server as server_module
from api.inactivity_watch_service import InactivityWatcherConfig, InactivityWatcherService
from core.engine.scheduler import SoneScheduler
from core.memory.schema import Book, Chapter, Verse, WatcherRun, WorkPackage, create_session_factory


class _FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.registered: list[dict] = []

    def register_periodic_job(
        self,
        *,
        name: str,
        callback,
        interval_seconds: int,
        startup_delay_seconds: int = 0,
    ):
        self.registered.append(
            {
                "name": name,
                "callback": callback,
                "interval_seconds": interval_seconds,
                "startup_delay_seconds": startup_delay_seconds,
            }
        )
        return self.registered[-1]

    def start_background(self):
        self.started = True


def _seed_old_activity(session_factory) -> None:
    session = session_factory()
    try:
        old_at = datetime.now(UTC) - timedelta(days=8)
        book = Book(title="Book of Beginnings")
        session.add(book)
        session.flush()
        chapter = Chapter(book_id=book.id, title=f"Session {old_at.date().isoformat()}")
        session.add(chapter)
        session.flush()
        session.add(
            Verse(
                chapter_id=chapter.id,
                verse_number=1,
                content='{"__namespace":"notes","title":"old","body":"old"}',
                speaker="User",
                created_at=old_at,
            )
        )
        session.add(
            WorkPackage(
                id="wp_old_001",
                title="Old package",
                description="pending",
                payload={},
                context_tag="work",
                status="READY",
                created_at=old_at,
                updated_at=old_at,
            )
        )
        session.commit()
    finally:
        session.close()


def test_server_startup_registers_inactivity_job(monkeypatch):
    fake_scheduler = _FakeScheduler()
    monkeypatch.setattr(server_module.settings, "enable_watchers", True)
    monkeypatch.setattr(server_module.settings, "watcher_interval_seconds", 111)
    monkeypatch.setattr(server_module.settings, "watcher_startup_delay_seconds", 7)

    registered = server_module.register_watcher_jobs(target_scheduler=fake_scheduler)
    assert registered is True
    assert len(fake_scheduler.registered) == 1
    assert fake_scheduler.registered[0]["name"] == "inactivity_watcher"
    assert fake_scheduler.registered[0]["interval_seconds"] == 111
    assert fake_scheduler.registered[0]["startup_delay_seconds"] == 7


def test_scheduler_periodic_job_runs_single_tick(tmp_path):
    scheduler = SoneScheduler(db_path=f"sqlite:///{tmp_path / 'scheduler.db'}", poll_interval_seconds=1)
    calls: list[str] = []

    scheduler.register_periodic_job(
        name="watcher",
        callback=lambda: calls.append("ran"),
        interval_seconds=60,
        startup_delay_seconds=0,
    )

    first = scheduler.run_periodic_once()
    second = scheduler.run_periodic_once()

    assert first["executed"] == 1
    assert second["executed"] == 0
    assert calls == ["ran"]


def test_inactivity_service_runs_once_then_skips_with_cooldown_or_dedup(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'watcher_service.db'}"
    session_factory = create_session_factory(db_url)
    _seed_old_activity(session_factory)

    emitted_events: list[str] = []
    monkeypatch.setattr(
        "api.inactivity_watch_service.write_lifecycle_event",
        lambda event_type, payload, skill_id="watcher.inactivity": emitted_events.append(event_type),
    )

    service = InactivityWatcherService(
        db_path=db_url,
        config=InactivityWatcherConfig(
            enabled=True,
            threshold_days=7,
            cooldown_days=3,
            daily_limit=1,
            user_id="default",
        ),
    )

    first = service.run_once()
    second = service.run_once()

    assert first["ran"] is True
    assert first["triggered"] is True
    assert "INACTIVITY_CHECKED" in first["effects"]["ledger_events"]
    assert "INACTIVITY_TRIGGERED" in first["effects"]["ledger_events"]

    assert second["ran"] is True
    assert second["triggered"] is False
    assert second["reason"] in {"cooldown_active", "dedup_hit", "daily_rate_limited", "threshold_not_met"}

    session = session_factory()
    try:
        triggered_runs = (
            session.query(WatcherRun)
            .filter(WatcherRun.rule_id == "INACTIVITY_7D", WatcherRun.triggered.is_(True))
            .count()
        )
        assert triggered_runs == 1
    finally:
        session.close()

    assert "INACTIVITY_CHECKED" in emitted_events
