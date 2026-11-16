from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIALPULSE_", env_file=".env", extra="ignore")
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    retrieval: Literal["demo", "qdrant"] = "demo"
    qdrant_url: str = "http://localhost:6333"
    collection: str = "trialpulse"
    model_name: str = "FremyCompany/BioLORD-2023"
    artifact_dir: Path = Path("artifacts")
    fhir_dir: Path = Path("data/local/fhir")
    llm_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 30.0
    allowed_hosts: list[str] = ["*"]
    cors_origins: list[str] = []
    max_request_bytes: int = 5_000_000
    rate_limit_per_minute: int = 240
    request_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
