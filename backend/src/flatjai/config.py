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


class ModelProfile(BaseModel):
    name: str
    base_url: str
    model: str
    context: int = 32768
    max_concurrency: int = 2
    json_schema: bool = True
    api_key: str = "not-needed"


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
