"""Evaluador Gemini con salida validada y trazabilidad de ejecución."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import logging
import time
import hashlib
import json
import re
from google import genai
from src.config import get_settings
from src.evaluation.schemas import OfferEvaluation
from src.cv.embeddings import _is_retryable_error, _retry_delay_seconds

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "evaluator_system.md"
FALLBACK_MODEL = "gemini-3.8-flash"
MAX_INLINE_RETRY_DELAY_SECONDS = 60


class GeminiEvaluationDeferred(RuntimeError):
    """La API indicó una espera extensa; se pausa sin bloquear el worker."""

    def __init__(self, message: str, retry_after_seconds: float, model: str):
        super().__init__(message)
        self.retry_after_seconds = max(0.0, float(retry_after_seconds))
        self.model = model


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _daily_quota_retry_seconds(message: str) -> float | None:
    """Extrae la espera de una cuota diaria agotada (p. ej. 22h9m16s)."""
    lowered = message.lower()
    if not any(marker in lowered for marker in (
        "requests per day limit exceeded",
        "per day limit exceeded",
        "daily limit exceeded",
        "generaterequestsperday",
    )):
        return None
    match = re.search(
        r"(?:(\\d+)\\s*h)?\\s*(?:(\\d+)\\s*m)?\\s*(?:(\\d+(?:\\.\\d+)?)\\s*s)?",
        message,
        flags=re.IGNORECASE,
    )
    if match and any(part is not None for part in match.groups()):
        hours, minutes, seconds = match.groups()
        return max(60.0, (int(hours or 0) * 3600) + (int(minutes or 0) * 60) + float(seconds or 0))
    return 24 * 3600.0


def _is_unavailable_model_error(exc: Exception) -> bool:
    """Detecta el 404 explícito de un modelo retirado/no habilitado."""
    message = str(exc).lower()
    return (
        ("404" in message or "not_found" in message)
        and ("no longer available" in message or "retired" in message)
    )


def evaluate_offer(
    offer: dict,
    cv_profile: dict,
    evidence_chunks: list[dict],
    *,
    client=None,
    model: str | None = None,
) -> dict:
    """Evalúa una oferta contra perfil y evidencia recuperada.

    La recuperación semántica se ejecuta fuera de esta función para poder
    probar el evaluador con evidencia controlada y reproducible.
    """
    settings = get_settings()
    if client is None:
        if not settings.gemini_api_key:
            raise ValueError("Falta GEMINI_API_KEY.")
        client = genai.Client(api_key=settings.gemini_api_key)

    model_name = model or settings.gemini_model
    prompt_version = hashlib.sha256(load_system_prompt().encode()).hexdigest()[:12]
    payload = {
        "offer": offer,
        "cv_profile": cv_profile,
        "retrieved_cv_evidence": [
            {"section": item.get("section"), "chunk_id": item.get("chunk_id"), "text": item.get("text")}
            for item in evidence_chunks
        ],
    }
    request = {
        "model": model_name,
        "contents": (load_system_prompt() + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)),
        "config": {
            "response_mime_type": "application/json",
            "response_schema": OfferEvaluation,
            "temperature": 0,
        },
    }
    response = None
    for attempt in range(5):
        try:
            response = client.models.generate_content(**request)
            break
        except Exception as exc:
            # Una cuota diaria agotada no es un fallo transitorio: no reintentar
            # cada oferta. Pausar la etapa y conservar todo lo persistido.
            quota_wait = _daily_quota_retry_seconds(str(exc))
            if quota_wait is not None:
                message = (
                    f"Gemini agotó la cuota diaria gratuita del modelo {model_name}. "
                    f"Google indicó esperar aproximadamente {quota_wait:.0f} segundos. "
                    "La evaluación se pausó; las ofertas pendientes se conservan."
                )
                raise GeminiEvaluationDeferred(message, quota_wait, model_name) from exc
            if _is_unavailable_model_error(exc) and model_name != FALLBACK_MODEL:
                logger.warning(
                    "El modelo Gemini %s ya no está disponible; se cambia automáticamente a %s.",
                    model_name, FALLBACK_MODEL,
                )
                model_name = FALLBACK_MODEL
                request["model"] = model_name
                continue
            if not _is_retryable_error(exc):
                raise
            delay = _retry_delay_seconds(exc, attempt)
            if delay > MAX_INLINE_RETRY_DELAY_SECONDS:
                message = (
                    f"Gemini solicitó esperar {delay:.0f} segundos para el modelo {model_name}. "
                    "La evaluación se pausó para no bloquear la aplicación; las ofertas pendientes "
                    "se conservan para reanudarlas en otra ejecución."
                )
                raise GeminiEvaluationDeferred(message, delay, model_name) from exc
            if attempt >= 4:
                raise
            logger.warning(
                "Gemini evaluación transitoria (%s); reintento %s/4 en %.1f s. Modelo=%s",
                type(exc).__name__, attempt + 1, delay, model_name,
            )
            time.sleep(delay)
    if response is None:
        raise RuntimeError("Gemini no devolvió respuesta de evaluación.")
    result = OfferEvaluation.model_validate_json(response.text).model_dump()
    return {
        "evaluation": result,
        "model": model_name,
        "prompt_version": prompt_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "cv_hash": cv_profile.get("cv_hash"),
        "offer_hash": offer.get("job_hash"),
        "evidence_chunk_ids": [item.get("chunk_id") for item in evidence_chunks],
    }
