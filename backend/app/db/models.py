"""SQLAlchemy 2.0 models for captured traces and their derived evaluations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class shared by the Phase 2 telemetry tables."""


class Trace(Base):
    """One root invocation, identified by its OpenTelemetry trace ID."""

    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNSET")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    spans: Mapped[list[Span]] = relationship(
        back_populates="trace", cascade="all, delete-orphan", order_by="Span.start_time"
    )
    eval_results: Mapped[list[EvalResult]] = relationship(
        back_populates="trace", cascade="all, delete-orphan"
    )


class Span(Base):
    """A completed OTel span belonging to one captured trace."""

    __tablename__ = "spans"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), index=True, nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNSET")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    trace: Mapped[Trace] = relationship(back_populates="spans")


class EvalResult(Base):
    """Asynchronous scores keyed to a captured trace."""

    __tablename__ = "eval_results"
    __table_args__ = (UniqueConstraint("trace_id", "metric_name", name="uq_eval_trace_metric"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), index=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    trace: Mapped[Trace] = relationship(back_populates="eval_results")


class AlertCooldown(Base):
    """Shared alert cooldown state across workers."""

    __tablename__ = "alert_cooldowns"

    metric_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    alerted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
