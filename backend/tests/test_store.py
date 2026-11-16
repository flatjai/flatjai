from datetime import UTC, datetime, timedelta

from flatjai.storage.store import Store


async def test_page_cache_returns_only_fresh_pages(store: Store):
    now = datetime.now(UTC)
    common = {"final_url": "u", "title": "t", "text": "x", "http_status": 200}
    await store.put_page(page_hash="old", url="https://a/1", fetched_at=now - timedelta(hours=30), **common)
    assert await store.fresh_page("https://a/1", timedelta(hours=24), now) is None
    await store.put_page(page_hash="new", url="https://a/1", fetched_at=now - timedelta(hours=1), **common)
    assert (await store.fresh_page("https://a/1", timedelta(hours=24), now)).page_hash == "new"


async def test_extraction_cache_is_unique_per_page_version_model(store: Store):
    now = datetime.now(UTC)
    await store.put_page(
        page_hash="h", url="u", final_url="u", title="t", text="x", http_status=200, fetched_at=now
    )
    key = {"page_hash": "h", "extractor_version": "v1", "model": "m"}
    first = await store.put_extraction(**key, data={"a": 1}, outcome="ok", dropped=[])
    second = await store.put_extraction(**key, data={"a": 2}, outcome="ok", dropped=[])
    assert first.id == second.id and second.data == {"a": 1}
    assert await store.extraction("h", "v2", "m") is None


async def test_events_replay_in_order(store: Store):
    await store.create_session("s")
    await store.create_run(
        id="r",
        session_id="s",
        brief="b",
        status="running",
        stage="understand",
        state={},
        model_profile="p",
        model="m",
    )
    for seq in (2, 1, 3):
        await store.add_event("r", seq, "progress", {"n": seq})
    assert [e.seq for e in await store.events("r")] == [1, 2, 3]
