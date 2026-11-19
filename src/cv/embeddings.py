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
    batch_size: int = 40,
) -> list[list[float]]:
    """Genera embeddings por lotes con modelo y dimensión fijos."""
    if not texts:
        return []
    if output_dimensionality != EMBEDDING_DIMENSIONS:
        raise ValueError("Radar 2.0 fija los embeddings en 3.072 dimensiones.")
    if not 1 <= batch_size <= 250:
        raise ValueError("batch_size debe estar entre 1 y 250.")
    if any(not text.strip() for text in texts):
        raise ValueError("No se pueden generar embeddings de textos vacíos.")

    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response: Any = client.models.embed_content(
            model=model,
            contents=batch,
            config={
                "task_type": task_type,
                "output_dimensionality": output_dimensionality,
            },
        )
        embeddings = getattr(response, "embeddings", None)
        if not embeddings or len(embeddings) != len(batch):
            raise RuntimeError("Gemini devolvió una cantidad inesperada de embeddings.")
        for item in embeddings:
            vector = list(item.values)
            if len(vector) != output_dimensionality:
                raise RuntimeError(
                    f"Gemini devolvió {len(vector)} dimensiones; se esperaban {output_dimensionality}."
                )
            vectors.append(vector)
    return vectors
