"""Adaptador Gemini para generar embeddings reproducibles."""
from __future__ import annotations

from typing import Any, Literal
from google import genai

EMBEDDING_DIMENSIONS = 3072
EmbeddingTask = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


def embed_texts(
    texts: list[str],
    api_key: str,
    model: str = "gemini-embedding-001",
    *,
    task_type: EmbeddingTask = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = EMBEDDING_DIMENSIONS,
) -> list[list[float]]:
    """Genera embeddings de documentos o consultas con dimensiones fijas.

    Para comparar vectores, todos deben usar el mismo modelo y dimensión.
    """
    if not texts:
        return []
    if output_dimensionality != EMBEDDING_DIMENSIONS:
        raise ValueError("Radar 2.0 fija los embeddings en 3.072 dimensiones.")
    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []
    for text in texts:
        if not text.strip():
            raise ValueError("No se pueden generar embeddings de textos vacíos.")
        response: Any = client.models.embed_content(
            model=model,
            contents=text,
            config={
                "task_type": task_type,
                "output_dimensionality": output_dimensionality,
            },
        )
        embedding = getattr(response, "embeddings", None)
        if not embedding:
            raise RuntimeError("Gemini no devolvió un embedding para uno de los fragmentos.")
        vector = list(embedding[0].values)
        if len(vector) != output_dimensionality:
            raise RuntimeError(
                f"Gemini devolvió {len(vector)} dimensiones; se esperaban {output_dimensionality}."
            )
        vectors.append(vector)
    return vectors
