"""Adaptador Gemini con reintentos y persistencia incremental por lote."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable, Literal

from google import genai

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS = 3072
DEFAULT_EMBEDDING_BATCH_SIZE = 40
DEFAULT_MAX_RETRIES = 4
EmbeddingTask = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


def _is_retryable_error(exc: Exception) -> bool:
    """Reconoce errores transitorios de cuota/servicio sin reintentar fallos de entrada."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    message = str(exc).upper()
    return status in (429, 500, 502, 503, 504) or any(
        marker in message
        for marker in ("429", "RESOURCE_EXHAUSTED", "UNAVAILABLE",
                       "INTERNAL", "DEADLINE_EXCEEDED", "SERVICE UNAVAILABLE")
    )


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    """Respeta el retryDelay indicado por Google; usa backoff si no viene informado."""
    message = str(exc)
    patterns = (
        r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s",
        r"retryDelay[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*s",
        r"retry_after[^0-9]*([0-9]+(?:\.[0-9]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return max(0.1, float(match.group(1)))
    return float(min(2 ** (attempt + 1), 30))


def embed_texts(
    texts: list[str],
    api_key: str,
    model: str = "gemini-embedding-001",
    *,
    task_type: EmbeddingTask = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = EMBEDDING_DIMENSIONS,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    on_batch: Callable[[int, list[str], list[list[float]]], None] | None = None,
) -> list[list[float]]:
    """Genera embeddings por lotes.

    on_batch se ejecuta inmediatamente después de validar cada respuesta. El
    consumidor puede persistir ese lote antes de solicitar el siguiente, de
    modo que un 429 posterior no obliga a recalcular lo ya completado.
    """
    if not texts:
        return []
    if output_dimensionality != EMBEDDING_DIMENSIONS:
        raise ValueError("Radar 2.0 fija los embeddings en 3.072 dimensiones.")
    if not 1 <= batch_size <= 250:
        raise ValueError("batch_size debe estar entre 1 y 250.")
    if max_retries < 0 or max_retries > 8:
        raise ValueError("max_retries debe estar entre 0 y 8.")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("No se pueden generar embeddings de textos vacíos.")

    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response: Any = None
        for attempt in range(max_retries + 1):
            try:
                response = client.models.embed_content(
                    model=model,
                    contents=batch,
                    config={
                        "task_type": task_type,
                        "output_dimensionality": output_dimensionality,
                    },
                )
                break
            except Exception as exc:
                if attempt >= max_retries or not _is_retryable_error(exc):
                    raise
                delay = _retry_delay_seconds(exc, attempt)
                logger.warning(
                    "Gemini embeddings transitorio (%s); reintento %s/%s en %.1f s. Modelo=%s",
                    type(exc).__name__, attempt + 1, max_retries, delay, model,
                )
                time.sleep(delay)

        embeddings = getattr(response, "embeddings", None)
        if not embeddings or len(embeddings) != len(batch):
            raise RuntimeError("Gemini devolvió una cantidad inesperada de embeddings.")
        batch_vectors: list[list[float]] = []
        for item in embeddings:
            vector = list(item.values)
            if len(vector) != output_dimensionality:
                raise RuntimeError(
                    f"Gemini devolvió {len(vector)} dimensiones; se esperaban {output_dimensionality}."
                )
            batch_vectors.append(vector)
        if on_batch:
            on_batch(start, batch, batch_vectors)
        vectors.extend(batch_vectors)
    return vectors
