"""Pipeline de preparación y persistencia de una versión del CV."""
from __future__ import annotations

from src.config import get_settings
from src.cv.embeddings import embed_texts
from src.cv.pipeline import CHUNKER_VERSION, prepare_cv_chunks
from src.db.repository import save_cv_snapshot


def ingest_cv(pdf_path: str, *, client, user_id: str) -> dict:
    """Lee PDF local, segmenta, genera vectores y guarda snapshot en Supabase."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY.")
    if settings.embedding_dimensions != 3072:
        raise ValueError("GEMINI_EMBEDDING_DIMENSIONS debe ser 3072.")

    prepared = prepare_cv_chunks(pdf_path)
    chunks = prepared["chunks"]
    vectors = embed_texts(
        [chunk["text"] for chunk in chunks],
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        task_type="RETRIEVAL_DOCUMENT",
    )
    saved = save_cv_snapshot(
        client,
        user_id=user_id,
        cv_metadata=prepared["cv"],
        chunks=chunks,
        embeddings=vectors,
        embedding_model=settings.embedding_model,
        chunker_version=CHUNKER_VERSION,
    )
    return {**saved, "cv": prepared["cv"], "embedding_model": settings.embedding_model}
