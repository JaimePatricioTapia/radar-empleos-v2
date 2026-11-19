from types import SimpleNamespace
import pytest

from src.db.repository import save_cv_snapshot, upsert_job_offer


def test_save_cv_snapshot_rejects_mismatched_embeddings():
    with pytest.raises(ValueError, match="exactamente un embedding"):
        save_cv_snapshot(
            object(),
            user_id="user-1",
            cv_metadata={"cv_hash": "abc"},
            chunks=[{"chunk_id": "c1", "text": "texto"}],
            embeddings=[],
            embedding_model="gemini-embedding-001",
            chunker_version="1.0.0",
        )


def test_save_cv_snapshot_rejects_wrong_dimensions():
    with pytest.raises(ValueError, match="3.072"):
        save_cv_snapshot(
            object(),
            user_id="user-1",
            cv_metadata={"cv_hash": "abc"},
            chunks=[{"chunk_id": "c1", "text": "texto"}],
            embeddings=[[0.1] * 768],
            embedding_model="gemini-embedding-001",
            chunker_version="1.0.0",
        )


def test_upsert_offer_requires_hash_and_description():
    with pytest.raises(ValueError, match="job_hash"):
        upsert_job_offer(object(), user_id="user-1", offer={"title": "Analista"})
