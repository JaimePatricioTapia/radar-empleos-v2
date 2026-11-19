"""Orquestación y versionamiento de artefactos derivados del CV."""
from __future__ import annotations
from src.cv.chunker import chunk_cv
from src.cv.reader import read_cv

CHUNKER_VERSION = "1.0.0"


def artifacts_need_rebuild(previous_manifest: dict | None, *, cv_hash: str, embedding_model: str, chunker_version: str = CHUNKER_VERSION) -> bool:
    """True si cambió CV, modelo, chunker o falta algún artefacto."""
    if not previous_manifest:
        return True
    return any((
        previous_manifest.get("cv_hash") != cv_hash,
        previous_manifest.get("embedding_model") != embedding_model,
        previous_manifest.get("chunker_version") != chunker_version,
        not previous_manifest.get("chunks_ready", False),
        not previous_manifest.get("embeddings_ready", False),
    ))


def prepare_cv_chunks(pdf_path: str, max_chars: int = 1200) -> dict:
    """Lee el CV y produce chunks. No llama a Gemini ni persiste información."""
    cv = read_cv(pdf_path)
    chunks = chunk_cv(cv["text"], cv["cv_hash"], max_chars=max_chars)
    return {
        "cv": {key: value for key, value in cv.items() if key != "text"},
        "chunks": chunks,
        "manifest": {
            "cv_hash": cv["cv_hash"],
            "chunker_version": CHUNKER_VERSION,
            "chunk_count": len(chunks),
            "chunks_ready": True,
            "embeddings_ready": False,
            "embedding_model": None,
        },
    }
