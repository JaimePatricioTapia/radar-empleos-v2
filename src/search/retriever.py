"""Recupera evidencia del CV mediante pgvector + Gemini."""
from __future__ import annotations

from typing import Any
from src.cv.embeddings import embed_texts


def retrieve_cv_evidence(
    query_text: str,
    *,
    client: Any,
    api_key: str,
    model: str = "gemini-embedding-001",
    limit: int = 8,
    cv_version_id: str | None = None,
) -> list[dict]:
    if not query_text.strip():
        raise ValueError("La consulta de recuperación no puede estar vacía.")
    if not 1 <= limit <= 50:
        raise ValueError("limit debe estar entre 1 y 50.")
    query_vector = embed_texts(
        [query_text],
        api_key=api_key,
        model=model,
        task_type="RETRIEVAL_QUERY",
    )[0]
    if len(query_vector) != 3072:
        raise ValueError(f"Se esperaban 3.072 dimensiones; se recibieron {len(query_vector)}.")
    response = client.rpc(
        "match_cv_chunks",
        {
            "query_embedding": query_vector,
            "match_count": limit,
            "filter_cv_version_id": cv_version_id,
            "filter_section": None,
        },
    ).execute()
    return response.data or []
