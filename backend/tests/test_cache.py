from datetime import timedelta

from conftest import LIST_URL

from flatjai.tools.cache import CachedSearcher
from flatjai.tools.portals import portal_for
from flatjai.tools.search import SearchError, portal_results


class Engine:
    def __init__(self):
        self.calls, self.mode = 0, "ok"

    async def search(self, query, portal=None, lang="en"):
        self.calls += 1
        if self.mode == "error":
            raise SearchError("too many requests")
        return [] if self.mode == "empty" else portal_results([{"url": LIST_URL}])


async def test_fresh_results_come_from_the_cache(store):
    engine = Engine()
    s = CachedSearcher(engine, store)
    first = await s.search("Hang Hau flat")
    assert await s.search("  hang hau   FLAT ") == first and engine.calls == 1


async def test_stale_results_are_served_when_the_engines_refuse(store):
    engine = Engine()
    s = CachedSearcher(engine, store, max_age=timedelta(0))
    await s.search("Hang Hau flat")
    for mode in ("error", "empty"):
        engine.mode = mode
        assert [r.url for r in await s.search("Hang Hau flat")] == [LIST_URL]


async def test_error_without_cache_is_raised(store):
    engine = Engine()
    engine.mode = "error"
    try:
        await CachedSearcher(engine, store).search("new query")
    except SearchError:
        return
    raise AssertionError("expected SearchError")


async def test_cached_results_pass_todays_filters(store):
    orlando = {
        "url": "https://amberstudent.com/places/the-rook-orlando-2608063813595",
        "title": "The Rook, Orlando",
        "snippet": "",
        "portal": "amber",
        "kind": "listing",
    }
    await store.cache_put("search", "en|amber|room hang hau", [orlando])
    amber = portal_for(orlando["url"])
    assert await CachedSearcher(Engine(), store).search("room Hang Hau", portal=amber) == []
