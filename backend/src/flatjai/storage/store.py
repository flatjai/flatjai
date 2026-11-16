"""Store: the only module that talks to the database. Agent code calls these methods, never SQL.

Postgres in development and production (`DATABASE_URL`), in-memory SQLite in unit tests.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from . import models as m


def make_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite"):  # unit tests: a file database, one connection per session
        return create_async_engine(url, poolclass=NullPool, connect_args={"timeout": 10})
    return create_async_engine(url, pool_pre_ping=True)


class Store:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self._s = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        """Tests only; real databases are migrated with Alembic."""
        async with self.engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

    # sessions and messages -------------------------------------------------------------------

    async def create_session(self, session_id: str) -> m.Session:
        async with self._s.begin() as s:
            row = m.Session(id=session_id, profile=None, asked=[])
            s.add(row)
        return row

    async def get_session(self, session_id: str) -> m.Session | None:
        async with self._s() as s:
            return await s.get(m.Session, session_id)

    async def update_session(self, session_id: str, **values: Any) -> None:
        async with self._s.begin() as s:
            await s.execute(update(m.Session).where(m.Session.id == session_id).values(**values))

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        async with self._s.begin() as s:
            s.add(m.Message(session_id=session_id, role=role, content=content))

    async def messages(self, session_id: str) -> list[m.Message]:
        async with self._s() as s:
            q = select(m.Message).where(m.Message.session_id == session_id).order_by(m.Message.id)
            return list((await s.scalars(q)).all())

    # runs and events -------------------------------------------------------------------------

    async def create_run(self, **values: Any) -> m.Run:
        async with self._s.begin() as s:
            row = m.Run(**values)
            s.add(row)
        return row

    async def get_run(self, run_id: str) -> m.Run | None:
        async with self._s() as s:
            return await s.get(m.Run, run_id)

    async def run_by_key(self, client_key: str) -> m.Run | None:
        async with self._s() as s:
            return await s.scalar(select(m.Run).where(m.Run.client_key == client_key))

    async def save_run(self, run_id: str, **values: Any) -> None:
        async with self._s.begin() as s:
            await s.execute(update(m.Run).where(m.Run.id == run_id).values(**values))

    async def list_runs(self, limit: int = 30) -> list[m.Run]:
        async with self._s() as s:
            return list((await s.scalars(select(m.Run).order_by(m.Run.started_at.desc()).limit(limit))).all())

    async def unfinished_runs(self) -> list[m.Run]:
        async with self._s() as s:
            return list((await s.scalars(select(m.Run).where(m.Run.status == "running"))).all())

    async def add_event(self, run_id: str, seq: int, type: str, data: dict) -> None:
        async with self._s.begin() as s:
            s.add(m.RunEvent(run_id=run_id, seq=seq, type=type, data=data))

    async def events(self, run_id: str) -> list[m.RunEvent]:
        async with self._s() as s:
            q = select(m.RunEvent).where(m.RunEvent.run_id == run_id).order_by(m.RunEvent.seq)
            return list((await s.scalars(q)).all())

    # pages and extractions (caches) ----------------------------------------------------------

    async def fresh_page(self, url: str, max_age: timedelta, now: datetime) -> m.Page | None:
        async with self._s() as s:
            q = (
                select(m.Page)
                .where(m.Page.url == url, m.Page.fetched_at >= now - max_age)
                .order_by(m.Page.fetched_at.desc())
                .limit(1)
            )
            return await s.scalar(q)

    async def put_page(self, **values: Any) -> None:
        async with self._s.begin() as s:
            await s.merge(m.Page(**values))  # same bytes -> same hash -> same row

    async def extraction(self, page_hash: str, version: str, model: str) -> m.Listing | None:
        async with self._s() as s:
            q = select(m.Listing).where(
                m.Listing.page_hash == page_hash,
                m.Listing.extractor_version == version,
                m.Listing.model == model,
            )
            return await s.scalar(q)

    async def put_extraction(self, **values: Any) -> m.Listing:
        async with self._s.begin() as s:
            existing = await s.scalar(
                select(m.Listing).where(
                    m.Listing.page_hash == values["page_hash"],
                    m.Listing.extractor_version == values["extractor_version"],
                    m.Listing.model == values["model"],
                )
            )
            if existing:  # two runs extracted the same page at once: keep the first
                return existing
            row = m.Listing(**values)
            s.add(row)
        return row

    async def listings(self, ids: list[int]) -> list[m.Listing]:
        if not ids:
            return []
        async with self._s() as s:
            rows = {r.id: r for r in (await s.scalars(select(m.Listing).where(m.Listing.id.in_(ids)))).all()}
        return [rows[i] for i in ids if i in rows]

    async def put_shortlist(self, run_id: str, items: list[tuple[int, list[str]]]) -> None:
        async with self._s.begin() as s:
            for rank, (listing_id, reasons) in enumerate(items, start=1):
                await s.merge(
                    m.ShortlistItem(run_id=run_id, rank=rank, listing_id=listing_id, reasons=reasons)
                )

    # generic tool cache ----------------------------------------------------------------------

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    async def cache_get(self, namespace: str, key: str) -> m.CacheEntry | None:
        async with self._s.begin() as s:
            row = await s.get(m.CacheEntry, (namespace, self._hash(key)))
            if row is not None:
                row.hits += 1
            return row

    async def cache_put(self, namespace: str, key: str, value: Any) -> None:
        async with self._s.begin() as s:
            await s.merge(
                m.CacheEntry(
                    namespace=namespace, key_hash=self._hash(key), key=key, value=value, stored_at=m.utcnow()
                )
            )

    # traces ----------------------------------------------------------------------------------

    async def add_spans(self, spans: list[dict]) -> None:
        if not spans:
            return
        async with self._s.begin() as s:
            for sp in spans:
                await s.merge(m.Span(**sp))

    async def spans(self, run_id: str) -> list[m.Span]:
        async with self._s() as s:
            q = select(m.Span).where(m.Span.run_id == run_id).order_by(m.Span.started_at)
            return list((await s.scalars(q)).all())

    async def run_totals(self, run_id: str) -> dict:
        async with self._s() as s:
            q = select(
                m.Span.kind, func.count(), func.sum(m.Span.tokens_in), func.sum(m.Span.tokens_out)
            ).where(m.Span.run_id == run_id)
            rows = (await s.execute(q.group_by(m.Span.kind))).all()
        return {k: {"count": c, "tokens_in": ti or 0, "tokens_out": to or 0} for k, c, ti, to in rows}
