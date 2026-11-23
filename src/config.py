"""Configuración centralizada de Radar 2.0."""
from functools import lru_cache
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _setting(name: str, default=None):
    """Lee variables de entorno y, en Streamlit Cloud, st.secrets."""
    value = os.getenv(name)
    if value is not None:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = _setting("GEMINI_API_KEY")
    # Gemini 2.5 Flash fue retirado el 20-10-2026; 3.8 Flash es el reemplazo.
    gemini_model: str = _setting("GEMINI_MODEL", "gemini-3.8-flash")
    embedding_model: str = _setting("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    embedding_dimensions: int = int(_setting("GEMINI_EMBEDDING_DIMENSIONS", "3072"))
    # Topes internos de protección para la cuota gratuita; no son cuotas oficiales de Google.
    max_daily_job_chunks: int = int(_setting("RADAR_MAX_DAILY_JOB_CHUNKS", "250"))
    max_daily_evaluations: int = int(_setting("RADAR_MAX_DAILY_EVALUATIONS", "15"))
    cv_pdf_path: str | None = _setting("CV_PDF_PATH")
    supabase_url: str | None = _setting("SUPABASE_URL")
    # Debe ser una publishable/anon key. Nunca configurar service_role en la app.
    supabase_key: str | None = _setting("SUPABASE_KEY")
    app_env: str = _setting("APP_ENV", "development")
    log_level: str = _setting("LOG_LEVEL", "INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
