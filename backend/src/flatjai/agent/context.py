"""Everything a stage needs, passed as one object: tools, storage, events, tracer, budget, clock."""

import time
from dataclasses import dataclass, field
from typing import Protocol

from ..model_client import ModelClient
from ..storage.store import Store
from ..tools.fetch import Page
from ..tools.geocode import Geocoder
from ..tools.otp import TransitRouter
from ..tools.portals import Portal
from ..tools.search import SearchResult
from ..tracing import Tracer
from .events import EventBus
from .state import Budget


class PageSource(Protocol):
    async def fetch(self, url: str) -> Page: ...


class SearchSource(Protocol):
    async def search(
        self, query: str, portal: Portal | None = None, lang: str = "en"
    ) -> list[SearchResult]: ...


@dataclass
class Toolbox:
    model: ModelClient
    searcher: SearchSource
    fetcher: PageSource
    geocoder: "Geocoder | None" = None  # None: commute is not estimated (the area check stands in)
    router: "TransitRouter | None" = None  # None: the offline estimate (tools/transit.py)


@dataclass
class RunContext:
    run_id: str
    session_id: str
    brief: str
    tools: Toolbox
    store: Store
    bus: EventBus
    tracer: Tracer
    budget: Budget = field(default_factory=Budget)
    started: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def work_time_left(self) -> float:
        """Seconds left for stages other than Answer."""
        return self.budget.max_seconds - self.budget.answer_reserve_s - self.elapsed()

    def answer_time_left(self) -> float:
        return max(self.budget.max_seconds - self.elapsed(), 5.0)
