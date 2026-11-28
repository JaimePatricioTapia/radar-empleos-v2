"""Evaluador Gemini con salida validada, fallback ordenado y trazabilidad."""
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
MODEL_PRIORITY = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
)
FALLBACK_MODEL = MODEL_PRIORITY[0]  # Compatibilidad con imports existentes.
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
        r"retry in\s+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)",
        message,
        flags=re.IGNORECASE,
    )
    if match and any(part is not None for part in match.groups()):
        hours, minutes, seconds = match.groups()
        return max(60.0, (int(hours or 0) * 3600) + (int(minutes or 0) * 60) + float(seconds or 0))
    return 24 * 3600.0


def _is_unavailable_model_error(exc: Exception) -> bool:
    """Detecta un 404 que indica que el modelo no existe o no está habilitado."""
    message = str(exc).lower()
    return ("404" in message or "not_found" in message) and any(
        marker in message for marker in (
            "no longer available", "retired", "not found", "not supported",
            "is not available", "model is unavailable",
        )
    )


def _model_attempt_order(model: str | None) -> tuple[str, ...]:
    """Usa la prioridad solicitada; un override explícito se prueba primero."""
    if not model:
        return MODEL_PRIORITY
    return (model,) + tuple(candidate for candidate in MODEL_PRIORITY if candidate != model)


def evaluate_offer(
    offer: dict,
    cv_profile: dict,
    evidence_chunks: list[dict],
    *,
    client=None,
    model: str | None = None,
) -> dict:
    """Evalúa una oferta y cambia de modelo ante cuota o indisponibilidad.

    Los errores transitorios breves se reintentan en el mismo modelo. Si la
    cuota diaria o el rate limit exige una espera extensa, se prueba el siguiente
    modelo antes de pausar la evaluación.
    """
    settings = get_settings()
    if client is None:
        if not settings.gemini_api_key:
            raise ValueError("Falta GEMINI_API_KEY.")
        client = genai.Client(api_key=settings.gemini_api_key)

    prompt = load_system_prompt()
    model_order = _model_attempt_order(model)
    model_name = model_order[0]
    prompt_version = hashlib.sha256(prompt.encode()).hexdigest()[:12]
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
        "contents": (prompt + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)),
        "config": {
            "response_mime_type": "application/json",
            "response_schema": OfferEvaluation,
            "temperature": 0,
        },
    }
    response = None
    deferred_waits: list[tuple[float, str]] = []
    last_unavailable_error = None

    for model_index, candidate in enumerate(model_order):
        model_name = candidate
        request["model"] = model_name
        for attempt in range(5):
            try:
                response = client.models.generate_content(**request)
                break
            except Exception as exc:
                quota_wait = _daily_quota_retry_seconds(str(exc))
                if quota_wait is not None:
                    deferred_waits.append((quota_wait, model_name))
                    logger.warning(
                        "Cuota diaria agotada para Gemini %s; se prueba el siguiente modelo.",
                        model_name,
                    )
                    break

                if _is_unavailable_model_error(exc):
                    last_unavailable_error = exc
                    logger.warning(
                        "El modelo Gemini %s no está disponible; se prueba el siguiente modelo.",
                        model_name,
                    )
                    break

                if not _is_retryable_error(exc):
                    raise

                delay = _retry_delay_seconds(exc, attempt)
                if delay > MAX_INLINE_RETRY_DELAY_SECONDS:
                    deferred_waits.append((delay, model_name))
                    logger.warning(
                        "Gemini %s requiere esperar %.1f s; se prueba el siguiente modelo.",
                        model_name, delay,
                    )
                    break

                if attempt >= 4:
                    raise
                logger.warning(
                    "Gemini evaluación transitoria (%s); reintento %s/4 en %.1f s. Modelo=%s",
                    type(exc).__name__, attempt + 1, delay, model_name,
                )
                time.sleep(delay)

            if response is not None:
                break

        if response is not None:
            break

    if response is None:
        if deferred_waits:
            retry_after, deferred_model = min(deferred_waits, key=lambda item: item[0])
            message = (
                "Los modelos Gemini disponibles alcanzaron sus cuotas o límites temporales. "
                f"La evaluación se pausó; vuelva a intentarlo en aproximadamente {retry_after:.0f} segundos. "
                "Las ofertas pendientes se conservan."
            )
            raise GeminiEvaluationDeferred(message, retry_after, deferred_model)
        if last_unavailable_error is not None:
            raise RuntimeError(
                "Ninguno de los modelos Gemini configurados está disponible. "
                "Revise los identificadores y el acceso de la API."
            ) from last_unavailable_error
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
