"""Run state and budgets. RunState is saved to `runs.state` after every stage, so a run interrupted
by a crash or restart continues from the last finished stage."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..tools.search import SearchResult

Stage = Literal["understand", "plan", "search", "read", "match", "reflect", "answer", "finished"]


@dataclass(frozen=True)
class Budget:
    """Per-run limits (40 model calls, 60 fetches, 90 s). When one runs out, the agent
    answers with what it has and says so."""

    max_seconds: float = 90.0
    answer_reserve_s: float = 20.0  # time kept back so the Answer stage can always run
    max_model_calls: int = 40
    max_fetches: int = 60
    max_rounds: int = 3  # plan -> search -> read rounds (the first plus up to two re-plans)
    reads_per_round: int = 8
    enough: int = 3  # re-plan if fewer homes than this fit
    shortlist_size: int = 5


class Check(BaseModel):
    """One hard constraint checked in code. ok=None means unknown (not stated on the listing)."""

    name: str
    ok: bool | None
    detail: str
    value: int | None = None  # the figure checked, e.g. the student's monthly share for "budget"


class Match(BaseModel):
    listing_id: int
    listing: dict[str, Any]  # Listing JSON
    cost: dict[str, Any]  # Cost JSON
    checks: list[Check]
    fetched_at: str
    dropped: list[str] = Field(default_factory=list)  # fields cleared by the grounding check
    duplicate_of: int | None = None

    @property
    def fits(self) -> bool:
        return self.duplicate_of is None and all(c.ok is not False for c in self.checks)


class RunState(BaseModel):
    stage: Stage = "understand"
    profile: dict[str, Any] | None = None
    round: int = 0
    queries_tried: list[str] = Field(default_factory=list)
    planned: list[str] = Field(default_factory=list)  # queries for the current round
    advice: str | None = None  # what Reflect asked the next Plan to change
    candidates: list[SearchResult] = Field(default_factory=list)  # found but not yet read
    read_urls: list[str] = Field(default_factory=list)
    matches: list[Match] = Field(default_factory=list)
    skipped: dict[str, int] = Field(default_factory=dict)
    fetches: int = 0
    queries: int = 0
    found: int = 0  # candidate listings found by all searches so far
    relaxations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # budget stops, resumes: shown in the answer

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def fits(self) -> list[Match]:
        return [m for m in self.matches if m.fits]

    def counters(self) -> dict[str, int]:
        return {
            "queries": self.queries,
            "candidates": self.found,
            "pages": len(self.read_urls),
            "cards": len(self.fits()),
        }
