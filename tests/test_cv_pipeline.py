from src.cv.chunker import chunk_cv
from src.cv.reader import read_cv
from src.cv.pipeline import artifacts_need_rebuild
import hashlib


def test_chunk_cv_preserves_content_and_metadata():
    text = "EXPERIENCIA PROFESIONAL\n\nAnalista de negocios. Levantamiento de requerimientos y gestión de backlog.\n\nFORMACIÓN\n\nIngeniería de Ejecución en Minas."
    cv_hash = hashlib.sha256(text.encode()).hexdigest()
    chunks = chunk_cv(text, cv_hash, max_chars=300)
    assert chunks
    assert all(chunk["cv_hash"] == cv_hash for chunk in chunks)
    assert "Analista de negocios" in " ".join(chunk["text"] for chunk in chunks)
    assert {chunk["section"] for chunk in chunks} >= {"experiencia", "formacion"}


def test_read_cv_rejects_missing_file(tmp_path):
    missing = tmp_path / "no-existe.pdf"
    try:
        read_cv(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Se esperaba FileNotFoundError")


def test_artifacts_rebuild_when_cv_hash_changes():
    manifest = {"cv_hash": "old", "embedding_model": "gemini-embedding-001", "chunker_version": "1.0.0", "chunks_ready": True, "embeddings_ready": True}
    assert artifacts_need_rebuild(manifest, cv_hash="new", embedding_model="gemini-embedding-001")


def test_artifacts_reused_when_versions_match():
    manifest = {"cv_hash": "same", "embedding_model": "gemini-embedding-001", "chunker_version": "1.0.0", "chunks_ready": True, "embeddings_ready": True}
    assert not artifacts_need_rebuild(manifest, cv_hash="same", embedding_model="gemini-embedding-001")
