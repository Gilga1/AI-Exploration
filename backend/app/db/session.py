"""Database setup and local completed-span persistence.

When no OTel Collector endpoint is configured the callback bridge uses this
small consumer directly.  It intentionally writes only completed spans, which
keeps the hot path compact and avoids exposing half-finished trace records.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any, Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base, Span, Trace


def get_database_url() -> str:
    """Use an explicit database URL or a repository-local SQLite dev store."""

    configured = os.getenv("DATABASE_URL") or get_settings().database_url
    if not configured:
        return "sqlite:///./traces.db"
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql+psycopg://", 1)
    if configured.startswith("postgresql://"):
        return configured.replace("postgresql://", "postgresql+psycopg://", 1)
    return configured


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide synchronous SQLAlchemy engine."""

    url = get_database_url()
    is_sqlite = url.startswith("sqlite")
    # SQLite: allow cross-thread reuse and tolerate brief write contention
    # from FastAPI's threadpool / background eval tasks (L2 fix). Without a
    # busy timeout, concurrent spans are silently dropped by callers that
    # swallow persistence errors.
    connect_args: dict[str, Any] = (
        {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
    )
    engine = create_engine(
        url, future=True, pool_pre_ping=not is_sqlite, connect_args=connect_args
    )
    if is_sqlite:
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Build sessions lazily so settings are available during app import."""

    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


_init_lock = threading.Lock()
_init_done = False


def init_db() -> None:
    """Create tables once per process (L2 fix: create_all on every span caused
    concurrent lock-upgrade deadlocks on SQLite)."""

    global _init_done
    if _init_done:
        return
    with _init_lock:
        if _init_done:
            return
        Base.metadata.create_all(bind=get_engine())
        _init_done = True


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a transaction and roll it back if the caller raises."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def persist_completed_span(
    *,
    trace_id: str,
    span_id: str,
    parent_span_id: str | None,
    name: str,
    kind: str,
    start_time: datetime,
    end_time: datetime,
    duration_ms: float,
    status: str,
    attributes: dict[str, Any],
    is_root: bool,
) -> None:
    """Upsert one completed span and complete its trace for a root span."""

    init_db()
    with session_scope() as session:
        trace_record = session.get(Trace, trace_id)
        if trace_record is None:
            trace_record = Trace(
                id=trace_id,
                name=name if is_root else "rag.invoke",
                start_time=start_time,
                status="UNSET",
                attributes={},
            )
            session.add(trace_record)

        span_record = session.get(Span, span_id)
        if span_record is None:
            span_record = Span(
                id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=name,
                kind=kind,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                status=status,
                attributes=attributes,
            )
            session.add(span_record)
        else:
            span_record.end_time = end_time
            span_record.duration_ms = duration_ms
            span_record.status = status
            span_record.attributes = attributes

        if is_root:
            trace_record.name = name
            trace_record.start_time = start_time
            trace_record.end_time = end_time
            trace_record.duration_ms = duration_ms
            trace_record.status = status
            trace_record.attributes = attributes
