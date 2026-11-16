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
