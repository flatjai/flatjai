"""Settings and model profiles (models.yaml)."""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR.parent / ".env", extra="ignore")

    fj_model: str = "local"
    database_url: str = "postgresql+psycopg://flatjai:flatjai@localhost:5432/flatjai"
    models_file: Path = BACKEND_DIR / "models.yaml"

    # Tools
    searxng_url: str = "http://localhost:8888"
    otp_url: str | None = None  # OpenTripPlanner (make otp-graph); unset: the offline commute estimate
    data_dir: Path = BACKEND_DIR.parent / "data"
    user_agent: str = "FlatJai/0.1 (HKUST CSIT6000V student project; 1 request per 2 s per site)"
    min_fetch_interval_s: float = 2.0  # per domain; robots.txt crawl-delay wins if longer
    page_text_max_chars: int = 16_000  # ~6K tokens of mixed English/Chinese before extraction

    # Frozen snapshot: pages and searches only from the cache, never the network (evaluation, demo)
    fj_offline: bool = False

    # Agent budgets (90 s per brief; a laptop model may need more, set RUN_MAX_SECONDS)
    run_max_seconds: float = 90.0

    # Experiment E2: switch off agent parts (agent/ablations.py), comma-separated; evaluation only
    fj_ablate: str = ""

    # Web UI origin allowed to call the API from the browser
    cors_origins: list[str] = ["http://localhost:3000"]


class ModelProfile(BaseModel):
    name: str
    base_url: str
    model: str
    context: int = 32768
    max_concurrency: int = 2
    json_schema: bool = True
    api_key: str = "not-needed"
    # Extra JSON merged into every request, e.g. to turn off Qwen3 "thinking" for typed calls
    extra_body: dict = {}
    # Guards against a runaway generation (constrained decoding can loop on whitespace)
    max_output_tokens: int = 1024
    request_timeout_s: float = 120.0


def load_profile(name: str, models_file: Path) -> ModelProfile:
    raw = yaml.safe_load(models_file.read_text())["models"]
    if name not in raw:
        raise ValueError(f"unknown model profile {name!r}; known: {sorted(raw)}")
    p = dict(raw[name])
    if "base_url_file" in p:
        url_file = (models_file.parent / p.pop("base_url_file")).resolve()
        if not url_file.exists():
            raise FileNotFoundError(
                f"{url_file} missing: start qwen-public-serve on TACC and paste SERVICE_BASE_URL into it"
            )
        p["base_url"] = url_file.read_text().strip()
    return ModelProfile(name=name, **p)


@lru_cache
def settings() -> Settings:
    return Settings()


@lru_cache
def active_profile() -> ModelProfile:
    s = settings()
    return load_profile(s.fj_model, s.models_file)
