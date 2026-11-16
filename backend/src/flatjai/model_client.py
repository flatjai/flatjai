"""One client for every model (Ollama, LM Studio, vLLM on TACC): OpenAI-compatible API.

typed_call() sends a JSON schema from a Pydantic model, validates the reply and gives the
model one repair retry with the validation error before failing visibly.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import ModelProfile
from .tracing import span

T = TypeVar("T", bound=BaseModel)


@dataclass
class CallStats:
    name: str
    ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    attempts: int = 0
    error: str | None = None
    queue_ms: float = 0.0  # time waiting for a free slot under the server's concurrency limit


class BudgetExhausted(Exception):
    """The run used all the model calls it may make."""


@dataclass
class ModelClient:
    profile: ModelProfile
    client: AsyncOpenAI | None = None
    calls: list[CallStats] = field(default_factory=list)
    semaphore: asyncio.Semaphore | None = None  # shared by every run: the server's concurrency limit
    call_limit: int | None = None  # per-run budget (40 model calls)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = AsyncOpenAI(
                base_url=self.profile.base_url,
                api_key=self.profile.api_key,
                timeout=self.profile.request_timeout_s,
                max_retries=0,  # retries are ours (one repair retry), not hidden in the SDK
            )
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.profile.max_concurrency)

    def for_run(self, call_limit: int | None = None) -> "ModelClient":
        """Same connection and concurrency limit, separate call log and budget (per run)."""
        return ModelClient(self.profile, client=self.client, semaphore=self.semaphore, call_limit=call_limit)

    @property
    def calls_left(self) -> int | None:
        return None if self.call_limit is None else self.call_limit - len(self.calls)

    async def typed_call(
        self, name: str, system: str, user: str, out: type[T], require_all_keys: bool = False
    ) -> T:
        if self.calls_left is not None and self.calls_left <= 0:
            raise BudgetExhausted(f"model call budget of {self.call_limit} used up")
        stats = CallStats(name=name)
        self.calls.append(stats)
        async with span(name, "model", model=self.profile.model, input=user) as sp:
            try:
                return await self._call(stats, system, user, out, sp.attrs, require_all_keys)
            finally:
                sp.tokens_in, sp.tokens_out = stats.tokens_in, stats.tokens_out
                sp.attrs |= {"attempts": stats.attempts, "queue_ms": round(stats.queue_ms, 1)}

    async def _call(
        self, stats: CallStats, system: str, user: str, out: type[T], attrs: dict, require_all_keys: bool
    ) -> T:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = (
            {
                "type": "json_schema",
                "json_schema": {"name": out.__name__, "schema": schema_for(out, require_all_keys)},
            }
            if self.profile.json_schema
            else {"type": "json_object"}
        )
        start = time.perf_counter()
        try:
            for attempt in (1, 2):
                stats.attempts = attempt
                waited = time.perf_counter()
                async with self.semaphore:
                    stats.queue_ms += (time.perf_counter() - waited) * 1000
                    resp = await self.client.chat.completions.create(
                        model=self.profile.model,
                        messages=messages,
                        response_format=response_format,
                        temperature=0,
                        max_tokens=self.profile.max_output_tokens,
                        extra_body=self.profile.extra_body or None,
                    )
                if resp.usage:
                    stats.tokens_in += resp.usage.prompt_tokens
                    stats.tokens_out += resp.usage.completion_tokens
                choice = resp.choices[0]
                text = choice.message.content or ""
                attrs["output"] = text
                if getattr(choice, "finish_reason", None) == "length":
                    # runaway output: do not feed it back; ask again for compact JSON
                    attrs["cut_off"] = attempt
                    if attempt == 2:
                        stats.error = "output hit max_tokens twice"
                        raise ValueError(stats.error)
                    messages = [*messages[:2], {"role": "user", "content": "Reply with compact JSON only."}]
                    continue
                try:
                    return out.model_validate_json(_strip_fences(text))
                except ValueError as e:  # JSON syntax error or pydantic ValidationError
                    if attempt == 2:
                        stats.error = str(e)
                        raise
                    messages += [
                        {"role": "assistant", "content": text},
                        {
                            "role": "user",
                            "content": f"That JSON is invalid:\n{e}\nReply with corrected JSON only.",
                        },
                    ]
            raise AssertionError("unreachable")
        finally:
            stats.ms = (time.perf_counter() - start) * 1000


def schema_for(model: type[BaseModel], require_all_keys: bool = False) -> dict:
    """The JSON schema sent for guided decoding.

    List fields carry maxItems (from Field(max_length=...)), so a model cannot loop on a list; that
    and max_tokens stop runaway outputs. require_all_keys makes every property required (optional ones
    stay nullable). Measured on qwen3:8b, 2026-11-16: it stops key-skipping, but on sparse briefs the
    model then fills every slot with invented values ("cheap room please" -> budget 3000, HKUST), so
    it is off by default and only worth it for schemas whose fields are all knowable from the input.
    """
    schema = model.model_json_schema()
    if not require_all_keys:
        return schema

    def visit(node: dict) -> None:
        if node.get("type") == "object" and "properties" in node:
            node["required"] = list(node["properties"])
            node.setdefault("additionalProperties", False)
        for value in node.values():
            if isinstance(value, dict):
                visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        visit(item)

    visit(schema)
    return schema


def _strip_fences(text: str) -> str:
    """Small local models sometimes wrap JSON in ``` fences or a <think> block."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    json.loads(text)  # surface plain syntax errors as ValueError early
    return text
