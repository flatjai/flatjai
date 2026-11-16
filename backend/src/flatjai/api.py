"""Request API. M0: health + a synchronous parse endpoint. M1 adds POST /runs + SSE events."""
from fastapi import FastAPI
from pydantic import BaseModel

from .agent.understand import parse_brief
from .config import active_profile
from .model_client import ModelClient
from .schemas import Profile

app = FastAPI(title="FlatJai", version="0.1.0")


class BriefIn(BaseModel):
    brief: str


@app.get("/health")
async def health() -> dict:
    p = active_profile()
    return {"status": "ok", "model_profile": p.name, "model": p.model, "base_url": p.base_url}


@app.post("/parse", response_model=Profile)
async def parse(body: BriefIn) -> Profile:
    return await parse_brief(ModelClient(active_profile()), body.brief)
