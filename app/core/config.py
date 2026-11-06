"""Central settings, loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BUILDDOC_", extra="ignore")

    app_name: str = "BuildDoc AI"
    data_dir: Path = ROOT_DIR / "data"
    output_dir: Path = ROOT_DIR / "outputs"

    # --- OCR -------------------------------------------------------------- #
    ocr_enabled: bool = True
    ocr_lang: str = "en"
    ocr_dpi: int = 200
    # Pages with fewer native-text chars than this are treated as scanned.
    ocr_min_chars_per_page: int = 50

    # --- LLM -------------------------------------------------------------- #
    # "none" -> rule-based extraction + template explanations only
    # "openai" -> any OpenAI-compatible endpoint (OpenAI, vLLM/Ollama serving Qwen2.5)
    llm_provider: str = "none"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "not-needed"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_temperature: float = 0.0

    # --- Validation ------------------------------------------------------- #
    numeric_tolerance_pct: float = 2.0     # differences within this are "within tolerance"
    review_confidence_threshold: float = 0.80

    # --- API -------------------------------------------------------------- #
    api_url: str = "http://localhost:8000"   # used by the Streamlit frontend


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.output_dir.mkdir(parents=True, exist_ok=True)
    return s
