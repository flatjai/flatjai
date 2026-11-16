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
from pydantic import BaseModel, ValidationError

from .config import ModelProfile

T = TypeVar("T", bound=BaseModel)


@dataclass
class CallStats:
    name: str
    ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    attempts: int = 0
    error: str | None = None


@dataclass
class ModelClient:
    profile: ModelProfile
    client: AsyncOpenAI | None = None
    calls: list[CallStats] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = AsyncOpenAI(base_url=self.profile.base_url, api_key=self.profile.api_key)
        self._sem = asyncio.Semaphore(self.profile.max_concurrency)

    async def typed_call(self, name: str, system: str, user: str, out: type[T]) -> T:
        stats = CallStats(name=name)
        self.calls.append(stats)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        response_format = (
            {"type": "json_schema", "json_schema": {"name": out.__name__, "schema": out.model_json_schema()}}
            if self.profile.json_schema
            else {"type": "json_object"}
        )
        start = time.perf_counter()
        try:
            for attempt in (1, 2):
                stats.attempts = attempt
                async with self._sem:
                    resp = await self.client.chat.completions.create(
                        model=self.profile.model,
                        messages=messages,
                        response_format=response_format,
                        temperature=0,
                    )
                if resp.usage:
                    stats.tokens_in += resp.usage.prompt_tokens
                    stats.tokens_out += resp.usage.completion_tokens
                text = resp.choices[0].message.content or ""
                try:
                    return out.model_validate_json(_strip_fences(text))
                except ValidationError as e:
                    if attempt == 2:
                        stats.error = str(e)
                        raise
                    messages += [
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": f"That JSON is invalid:\n{e}\nReply with corrected JSON only."},
                    ]
            raise AssertionError("unreachable")
        finally:
            stats.ms = (time.perf_counter() - start) * 1000


def _strip_fences(text: str) -> str:
    """Small local models sometimes wrap JSON in ``` fences or a <think> block."""
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    json.loads(text)  # surface plain syntax errors as ValueError early
    return text
