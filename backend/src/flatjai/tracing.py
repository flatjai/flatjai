"""Lightweight tracer: every stage, model call and tool call becomes a span.

    async with span("fetch", "tool", url=url) as s:
        ...
        s.attrs["cache"] = "hit"

The active tracer and the current span live in context variables, so the model client and the tools
open spans without being handed a tracer, and asyncio tasks inherit the parent span they were
created under. Outside a run (CLI checks, unit tests of a single tool) spans are no-ops.
Finished spans are buffered and written to Postgres by the agent loop after each stage.
"""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

MAX_ATTR_CHARS = 4000


@dataclass
class SpanRecord:
    name: str
    kind: str  # stage | model | tool
    parent_id: str | None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)

    def row(self, run_id: str) -> dict:
        return {
            "id": self.id,
            "run_id": run_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "started_at": self.started_at,
            "ms": round(self.ms, 1),
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "error": self.error,
            "attrs": {k: clip(v) for k, v in self.attrs.items()},
        }


class Tracer:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.finished: list[SpanRecord] = []

    def drain(self) -> list[dict]:
        rows, self.finished = [r.row(self.run_id) for r in self.finished], []
        return rows


_tracer: ContextVar[Tracer | None] = ContextVar("tracer", default=None)
_current: ContextVar[SpanRecord | None] = ContextVar("span", default=None)


def activate(tracer: Tracer) -> None:
    """Make `tracer` the active one for this task and the tasks it creates."""
    _tracer.set(tracer)


@asynccontextmanager
async def span(name: str, kind: str, **attrs: Any) -> AsyncIterator[SpanRecord]:
    parent = _current.get()
    record = SpanRecord(name=name, kind=kind, parent_id=parent.id if parent else None, attrs=dict(attrs))
    token = _current.set(record)
    start = time.perf_counter()
    try:
        yield record
    except asyncio.CancelledError:
        record.attrs["cancelled"] = True  # stopped on purpose (enough homes found, time budget)
        raise
    except BaseException as e:
        record.error = f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        record.ms = (time.perf_counter() - start) * 1000
        _current.reset(token)
        if (tracer := _tracer.get()) is not None:
            tracer.finished.append(record)


def clip(value: Any, limit: int = MAX_ATTR_CHARS) -> Any:
    """Keep span attributes small: long strings and large structures are truncated."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"… [{len(value) - limit} more chars]"
    if isinstance(value, int | float | bool) or value is None:
        return value
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= limit else clip(text, limit)
