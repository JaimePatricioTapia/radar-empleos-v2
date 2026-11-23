"""Pipeline de preparación y persistencia de una versión del CV."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from src.config import get_settings
from src.cv.embeddings import embed_texts
from src.cv.pipeline import CHUNKER_VERSION, prepare_cv_chunks
from src.db.repository import save_cv_snapshot

MAX_CV_BYTES = 15 * 1024 * 1024


def _persist_prepared(prepared: dict, *, client, user_id: str) -> dict:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY.")
    if settings.embedding_dimensions != 3072:
        raise ValueError("GEMINI_EMBEDDING_DIMENSIONS debe ser 3072.")

    # Caché por hash del CV y modelo: no recalcular embeddings si la versión
    # activa ya tiene todos sus fragmentos persistidos.
    cv_hash = prepared["cv"]["cv_hash"]
    existing_versions = (
        client.table("cv_versions")
        .select("id,is_active,embedding_model,embedding_dimensions")
        .eq("user_id", user_id)
        .eq("cv_hash", cv_hash)
        .eq("embedding_model", settings.embedding_model)
        .eq("embedding_dimensions", 3072)
        .limit(1).execute().data or []
    )
    chunks = prepared["chunks"]
    if existing_versions:
        version = existing_versions[0]
        existing_chunks = (
            client.table("cv_chunks").select("id")
            .eq("user_id", user_id).eq("cv_version_id", version["id"])
            .limit(len(chunks) + 1).execute().data or []
        )
        if len(existing_chunks) >= len(chunks):
            if not version.get("is_active"):
                (client.table("cv_versions").update({"is_active": False})
                 .eq("user_id", user_id).neq("id", version["id"]).execute())
                (client.table("cv_versions").update({"is_active": True})
                 .eq("user_id", user_id).eq("id", version["id"]).execute())
            return {
                "cv_version_id": version["id"], "cv_hash": cv_hash,
                "chunk_count": len(chunks), "cached": True,
                "embedding_model": settings.embedding_model,
            }

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


def ingest_cv(pdf_path: str, *, client, user_id: str) -> dict:
    """Lee un PDF local, genera embeddings y guarda solo artefactos derivados."""
    return _persist_prepared(prepare_cv_chunks(pdf_path), client=client, user_id=user_id)


def ingest_cv_upload(file_bytes: bytes, filename: str, *, client, user_id: str) -> dict:
    """Procesa un PDF cargado desde el navegador y elimina siempre el temporal."""
    if not filename.lower().endswith(".pdf"):
        raise ValueError("El archivo debe tener extensión PDF.")
    if not file_bytes:
        raise ValueError("El archivo está vacío.")
    if len(file_bytes) > MAX_CV_BYTES:
        raise ValueError("El CV supera el máximo permitido de 15 MB.")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="radar_cv_", suffix=".pdf", delete=False) as temp:
            temp.write(file_bytes)
            temp.flush()
            temp_path = temp.name
        prepared = prepare_cv_chunks(temp_path)
        prepared["cv"]["filename"] = Path(filename).name
        return _persist_prepared(prepared, client=client, user_id=user_id)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
