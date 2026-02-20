from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)

    book = relationship("Book", back_populates="chapters")
    verses = relationship("Verse", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("book_id", "title", name="uq_chapter_book_title"),)


class Verse(Base):
    __tablename__ = "verses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False, index=True)
    verse_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    speaker = Column(String(64), nullable=False, default="Unknown")
    perspective = Column(String(64), nullable=True)
    is_constitution_active = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    chapter = relationship("Chapter", back_populates="verses")

    __table_args__ = (
        UniqueConstraint("chapter_id", "verse_number", name="uq_verse_chapter_number"),
    )


class SonECommand(Base):
    __tablename__ = "sone_commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command_id = Column(String(128), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(32), nullable=False)  # shell | python | http | workflow
    priority = Column(String(8), nullable=False, default="P3")
    payload = Column(JSON, nullable=False)
    schedule_type = Column(String(32), nullable=False, default="immediate")
    schedule_value = Column(String(255), nullable=False, default="")
    dependencies = Column(JSON, nullable=False, default=list)
    timeout = Column(Integer, nullable=False, default=30)
    retry_count = Column(Integer, nullable=False, default=0)
    retry_delay = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(32), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatTimelineMessage(Base):
    __tablename__ = "chat_timeline_messages"

    id = Column(String(64), primary_key=True)
    role = Column(String(16), nullable=False, index=True)  # user | sophia
    content = Column(Text, nullable=False)
    context_tag = Column(String(128), nullable=False, default="general", index=True)
    importance = Column(Float, nullable=False, default=0.5)
    emotion_signal = Column(String(64), nullable=True)
    linked_cluster = Column(String(128), nullable=True, index=True)
    linked_node = Column(String(128), nullable=True)
    meta = Column(JSON, nullable=True)
    status = Column(String(16), nullable=False, default="normal", index=True)  # normal | pending | escalated
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class QuestionPool(Base):
    __tablename__ = "question_pool"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(String(128), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=False)
    hit_count = Column(Integer, nullable=False, default=0)
    risk_score = Column(Float, nullable=False, default=0.0)
    evidence = Column(JSON, nullable=False, default=list)
    linked_nodes = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="collecting", index=True)  # collecting | ready_to_ask | asked
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_asked_at = Column(DateTime(timezone=True), nullable=True)
    asked_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkPackage(Base):
    __tablename__ = "work_packages"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    context_tag = Column(String(128), nullable=False, default="work", index=True)
    status = Column(String(32), nullable=False, default="READY", index=True)
    linked_node = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('READY','IN_PROGRESS','DONE','BLOCKED','FAILED')",
            name="ck_work_package_status",
        ),
    )


class MindItem(Base):
    __tablename__ = "mind_items"

    id = Column(String(128), primary_key=True)
    type = Column(String(32), nullable=False, index=True)  # TASK | QUESTION_CLUSTER | ALERT | FOCUS
    title = Column(String(255), nullable=False)
    summary_120 = Column(String(120), nullable=False, default="")
    priority = Column(Integer, nullable=False, default=0, index=True)
    risk_score = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    linked_bits = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    source_events = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="active", index=True)  # active | parked | done
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_mind_item_priority_range"),
        CheckConstraint("risk_score >= 0.0 AND risk_score <= 1.0", name="ck_mind_item_risk_range"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_mind_item_confidence_range"),
        CheckConstraint("status IN ('active','parked','done')", name="ck_mind_item_status"),
    )


class MindWorkingLog(Base):
    __tablename__ = "mind_working_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    line = Column(String(80), nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    item_id = Column(String(128), nullable=True, index=True)
    delta_priority = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class MindLearningRollup(Base):
    __tablename__ = "mind_learning_rollups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rollup_type = Column(String(32), nullable=False, index=True)  # TOTAL | DAILY | WINDOW_24H | TOP_PATTERNS
    bucket_key = Column(String(64), nullable=False, index=True)  # all | YYYY-MM-DD | rolling
    payload = Column(JSON, nullable=False, default=dict)
    source_event_count = Column(Integer, nullable=False, default=0)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("rollup_type", "bucket_key", name="uq_mind_learning_rollup_type_bucket"),
    )


class MindLearningRollupTrace(Base):
    __tablename__ = "mind_learning_rollup_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_date = Column(String(32), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    trace_id = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("event_date", "event_type", "trace_id", name="uq_mind_learning_rollup_trace"),
    )


class WatcherRun(Base):
    __tablename__ = "watcher_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, default="default", index=True)
    window_start_date = Column(String(32), nullable=False, default="")
    template_id = Column(String(32), nullable=False, default="")
    dedup_key = Column(String(255), nullable=False, unique=True, index=True)
    triggered = Column(Boolean, nullable=False, default=False, server_default="0")
    reason = Column(String(128), nullable=False, default="")
    result = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class UserRule(Base):
    __tablename__ = "user_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), nullable=False, index=True)
    value = Column(Text, nullable=False)
    type = Column(String(32), nullable=False, index=True)
    pinned = Column(Boolean, nullable=False, default=False, server_default="0")
    ttl_days = Column(Integer, nullable=False, default=30, server_default="30")
    hit_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("key", "type", name="uq_user_rule_key_type"),
        CheckConstraint("ttl_days >= 0", name="ck_user_rule_ttl_non_negative"),
    )


def _normalize_db_path(db_path: str) -> str:
    raw = str(db_path or "").strip()
    if not raw:
        return f"sqlite:///{Path('sophia.db').resolve()}"
    if raw.startswith("sqlite:///:memory:"):
        return raw
    if raw.startswith("sqlite:///"):
        return raw
    if raw.startswith("sqlite:"):
        # Handle malformed sqlite URI inputs such as "sqlite:/sophia.db"
        tail = raw[len("sqlite:") :].lstrip("/")
        if not tail:
            tail = "sophia.db"
        return f"sqlite:///{Path(tail).resolve()}"
    if raw.startswith("/"):
        return f"sqlite:///{raw}"
    return f"sqlite:///{Path(raw).resolve()}"


def create_memory_engine(db_path: str = "sqlite:///sophia.db"):
    normalized = _normalize_db_path(db_path)
    connect_args = {"check_same_thread": False} if normalized.startswith("sqlite:///") else {}
    return create_engine(normalized, connect_args=connect_args)


def create_session_factory(db_path: str = "sqlite:///sophia.db"):
    engine = create_memory_engine(db_path=db_path)
    Base.metadata.create_all(engine)
    _apply_lightweight_migrations(engine)
    return sessionmaker(bind=engine)


def utc_now() -> datetime:
    return datetime.utcnow()


def _apply_lightweight_migrations(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    def _table_columns(conn, table_name: str) -> set[str]:
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {str(row[1]) for row in rows}

    def _table_sql(conn, table_name: str) -> str:
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
        if not row:
            return ""
        value = row[0]
        return str(value) if value else ""

    migrations = {
        "chat_timeline_messages": [
            ("linked_cluster", "TEXT"),
            ("meta", "JSON"),
        ],
        "question_pool": [
            ("evidence", "JSON NOT NULL DEFAULT '[]'"),
            ("last_asked_at", "DATETIME"),
            ("asked_count", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mind_learning_rollups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rollup_type VARCHAR(32) NOT NULL,
                    bucket_key VARCHAR(64) NOT NULL,
                    payload JSON NOT NULL DEFAULT '{}',
                    source_event_count INTEGER NOT NULL DEFAULT 0,
                    computed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_mind_learning_rollup_type_bucket UNIQUE (rollup_type, bucket_key)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_mind_learning_rollups_rollup_type ON mind_learning_rollups(rollup_type)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_mind_learning_rollups_bucket_key ON mind_learning_rollups(bucket_key)"
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mind_learning_rollup_traces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_date VARCHAR(32) NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    trace_id VARCHAR(128) NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_mind_learning_rollup_trace UNIQUE (event_date, event_type, trace_id)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_mind_learning_rollup_traces_event_date ON mind_learning_rollup_traces(event_date)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_mind_learning_rollup_traces_event_type ON mind_learning_rollup_traces(event_type)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_mind_learning_rollup_traces_trace_id ON mind_learning_rollup_traces(trace_id)"
            )
        )

        for table_name, cols in migrations.items():
            existing = _table_columns(conn, table_name)
            if not existing:
                continue
            for column_name, ddl in cols:
                if column_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))

        work_columns = _table_columns(conn, "work_packages")
        if work_columns:
            work_sql = _table_sql(conn, "work_packages")
            if "ck_work_package_status" not in work_sql:
                conn.execute(text("DROP TABLE IF EXISTS work_packages_new"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE work_packages_new (
                            id TEXT PRIMARY KEY,
                            title VARCHAR(255) NOT NULL,
                            description TEXT,
                            payload JSON NOT NULL,
                            context_tag VARCHAR(128) NOT NULL DEFAULT 'work',
                            status VARCHAR(32) NOT NULL DEFAULT 'READY',
                            linked_node VARCHAR(128),
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            acknowledged_at DATETIME,
                            completed_at DATETIME,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT ck_work_package_status CHECK (status IN ('READY','IN_PROGRESS','DONE','BLOCKED','FAILED'))
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO work_packages_new (
                            id, title, description, payload, context_tag, status, linked_node,
                            created_at, acknowledged_at, completed_at, updated_at
                        )
                        SELECT
                            id,
                            title,
                            description,
                            payload,
                            context_tag,
                            CASE UPPER(COALESCE(status, ''))
                                WHEN 'READY' THEN 'READY'
                                WHEN 'ACKNOWLEDGED' THEN 'IN_PROGRESS'
                                WHEN 'IN_PROGRESS' THEN 'IN_PROGRESS'
                                WHEN 'COMPLETED' THEN 'DONE'
                                WHEN 'DONE' THEN 'DONE'
                                WHEN 'BLOCKED' THEN 'BLOCKED'
                                WHEN 'FAILED' THEN 'FAILED'
                                ELSE 'READY'
                            END AS status,
                            linked_node,
                            created_at,
                            acknowledged_at,
                            completed_at,
                            updated_at
                        FROM work_packages
                        """
                    )
                )
                conn.execute(text("DROP TABLE work_packages"))
                conn.execute(text("ALTER TABLE work_packages_new RENAME TO work_packages"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_work_packages_status ON work_packages(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_work_packages_context_tag ON work_packages(context_tag)"))
