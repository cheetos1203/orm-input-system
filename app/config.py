from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    data_dir: Path = Path("data")
    uploads_dir: Path = Path("data/uploads")
    outputs_dir: Path = Path("data/outputs")
    review_dir: Path = Path("data/review")

    enable_fallback_api: bool = False
    confidence_threshold: float = 0.75
    mark_min_fill: float = 0.30

    tesseract_cmd: str | None = None

    fallback_provider: str = "openai"
    fallback_api_url: str = "https://api.openai.com/v1/responses"
    fallback_api_key: str | None = None
    fallback_model: str = "gpt-4.1-mini"

    omr_choices: str = "ABCDE"
    row_group_tolerance: int = 18
    min_bubble_area: int = 120
    max_bubble_area: int = 3000

    debug_save_rois: bool = True

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = True
    app_workers: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
