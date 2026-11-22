"""typed_call against a fake OpenAI client: no model or network needed."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from flatjai.config import ModelProfile
from flatjai.model_client import ModelClient
from flatjai.schemas import Profile


class FakeCompletions:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    async def create(self, **kw):
        self.requests.append(kw)
        msg = SimpleNamespace(content=self.replies.pop(0))
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def client_with(*replies):
    fake = FakeCompletions(replies)
    oc = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return ModelClient(ModelProfile(name="t", base_url="http://x", model="m"), client=oc), fake


async def test_valid_json_returns_profile_and_sends_schema():
    mc, fake = client_with('{"budget_hkd_month": 9000, "campus": "HKUST"}')
    p = await mc.typed_call("parse_brief", "sys", "user", Profile)
    assert p.budget_hkd_month == 9000
    assert fake.requests[0]["response_format"]["type"] == "json_schema"
    assert mc.calls[0].attempts == 1 and mc.calls[0].tokens_in == 10


async def test_think_block_and_fences_are_stripped():
    mc, _ = client_with('<think>hmm</think>\n```json\n{"campus": "HKU"}\n```')
    assert (await mc.typed_call("x", "s", "u", Profile)).campus == "HKU"


async def test_one_repair_retry_then_success():
    mc, fake = client_with('{"budget_hkd_month": "lots"}', '{"budget_hkd_month": 8000}')
    assert (await mc.typed_call("x", "s", "u", Profile)).budget_hkd_month == 8000
    assert mc.calls[0].attempts == 2
    assert "invalid" in fake.requests[1]["messages"][-1]["content"]


async def test_fails_visibly_after_second_bad_reply():
    mc, _ = client_with('{"budget_hkd_month": "lots"}', '{"budget_hkd_month": "still"}')
    with pytest.raises(ValidationError):
        await mc.typed_call("x", "s", "u", Profile)
    assert mc.calls[0].error


async def test_broken_json_syntax_also_gets_the_repair_retry():
    mc, _ = client_with('{"campus": "HKUST"', '{"campus": "HKUST"}')
    assert (await mc.typed_call("x", "s", "u", Profile)).campus == "HKUST"
    assert mc.calls[0].attempts == 2


async def test_runaway_output_is_retried_without_feeding_it_back():
    fake = FakeCompletions(['{"campus": "HKUST"' + " " * 50, '{"campus": "HKUST"}'])
    reasons = iter(["length", "stop"])
    original = fake.create

    async def create(**kw):
        resp = await original(**kw)
        resp.choices[0].finish_reason = next(reasons)
        return resp

    fake.create = create
    oc = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    mc = ModelClient(ModelProfile(name="t", base_url="http://x", model="m"), client=oc)
    assert (await mc.typed_call("x", "s", "u", Profile)).campus == "HKUST"
    second = fake.requests[1]
    assert second["max_tokens"] == 1024
    assert all(m["role"] != "assistant" for m in second["messages"])


def test_schema_caps_lists_and_can_require_every_key():
    from flatjai.agent.answer import Shortlist
    from flatjai.model_client import schema_for

    assert schema_for(Profile)["properties"]["soft_preferences"]["maxItems"] == 6
    assert "required" not in schema_for(Profile)
    s = schema_for(Profile, require_all_keys=True)
    assert set(s["required"]) == set(s["properties"]) and s["additionalProperties"] is False
    assert s["properties"]["soft_preferences"]["maxItems"] == 6
    nested = schema_for(Shortlist, require_all_keys=True)["$defs"]["Pick"]
    assert nested["required"] == ["id", "reasons"]
