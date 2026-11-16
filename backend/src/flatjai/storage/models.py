"""Postgres tables. JSON columns are JSONB on Postgres and plain JSON on SQLite
(used by the unit tests). Schema changes go through Alembic: `make migrate`, migrations in
backend/migrations/versions/."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: Json, list[Any]: Json, datetime: DateTime(timezone=True)}


class Session(Base):
    """One conversation: the student's current profile and whether we already asked them something."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    profile: Mapped[dict[str, Any] | None]
    asked: Mapped[list[Any]] = mapped_column(default=list)  # hard constraints already asked about


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Run(Base):
    """One agent execution. `state` is the loop state after the last finished stage (resumable)."""

    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    client_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    brief: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # running | done | needs_input | error
    stage: Mapped[str] = mapped_column(String(20))
    state: Mapped[dict[str, Any]] = mapped_column(default=dict)
    model_profile: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]


class RunEvent(Base):
    """Every SSE event, so a client (or a resumed run) can replay from any sequence number."""

    __tablename__ = "events"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict[str, Any]]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Page(Base):
    """A fetched page; raw bytes live in the blob store under page_hash."""

    __tablename__ = "pages"
    page_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text, index=True)
    final_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int]
    fetched_at: Mapped[datetime]


class Listing(Base):
    """A verified extraction. Unique per (page, extractor version, model): this is the extraction cache."""

    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("page_hash", "extractor_version", "model"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_hash: Mapped[str] = mapped_column(ForeignKey("pages.page_hash"))
    extractor_version: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict[str, Any] | None]  # Listing JSON; null when the page is not a usable listing
    outcome: Mapped[str] = mapped_column(String(30))  # ok | not a listing | unsupported rent | ...
    dropped: Mapped[list[Any]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ShortlistItem(Base):
    __tablename__ = "shortlist_items"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    reasons: Mapped[list[Any]] = mapped_column(default=list)


class Span(Base):
    """Trace span: a stage, model call or tool call."""

    __tablename__ = "spans"
    __table_args__ = (Index("ix_spans_run_started", "run_id", "started_at"),)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    parent_id: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10))  # stage | model | tool
    started_at: Mapped[datetime]
    ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    attrs: Mapped[dict[str, Any]] = mapped_column(default=dict)  # inputs/outputs (truncated), counters


class CacheEntry(Base):
    """Generic tool cache (search now; geocode and commute in M3), keyed by namespace + key hash."""

    __tablename__ = "cache"
    namespace: Mapped[str] = mapped_column(String(20), primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(Text)  # readable key, for debugging
    value: Mapped[Any] = mapped_column(Json)
    stored_at: Mapped[datetime] = mapped_column(default=utcnow)
    hits: Mapped[int] = mapped_column(Integer, default=0)
