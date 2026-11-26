from pathlib import Path

import pytest

from src.cv import service


def test_upload_processes_pdf_in_temporary_file_and_removes_it(monkeypatch):
    observed = {}

    def fake_prepare(path):
        observed["path"] = Path(path)
        assert observed["path"].is_file()
        assert observed["path"].read_bytes() == b"%PDF-test"
        return {
            "cv": {"filename": observed["path"].name, "cv_hash": "abc"},
            "chunks": [{"text": "cv chunk"}],
        }

    def fake_persist(prepared, *, client, user_id):
        observed["filename"] = prepared["cv"]["filename"]
        observed["user_id"] = user_id
        return {"chunk_count": 1}

    monkeypatch.setattr(service, "prepare_cv_chunks", fake_prepare)
    monkeypatch.setattr(service, "_persist_prepared", fake_persist)

    result = service.ingest_cv_upload(
        b"%PDF-test", "Jaime CV.pdf", client=object(), user_id="user-1"
    )

    assert result["chunk_count"] == 1
    assert observed["filename"] == "Jaime CV.pdf"
    assert observed["user_id"] == "user-1"
    assert not observed["path"].exists()


@pytest.mark.parametrize(
    ("payload", "filename", "message"),
    [
        (b"%PDF", "cv.txt", "extensión PDF"),
        (b"", "cv.pdf", "vacío"),
        (b"x" * (service.MAX_CV_BYTES + 1), "cv.pdf", "15 MB"),
    ],
)
def test_upload_rejects_invalid_files(payload, filename, message):
    with pytest.raises(ValueError, match=message):
        service.ingest_cv_upload(
            payload, filename, client=object(), user_id="user-1"
        )


def test_same_cv_hash_reuses_persisted_embeddings(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="fake",
            embedding_dimensions=3072,
            embedding_model="gemini-embedding-001",
        ),
    )

    class Query:
        def __init__(self, table):
            self.table = table

        def select(self, *args):
            return self

        def eq(self, *args):
            return self

        def limit(self, *args):
            return self

        def execute(self):
            if self.table == "cv_versions":
                return SimpleNamespace(data=[{
                    "id": "cv-version-1",
                    "is_active": True,
                    "embedding_model": "gemini-embedding-001",
                    "embedding_dimensions": 3072,
                }])
            if self.table == "cv_chunks":
                return SimpleNamespace(data=[{"id": "chunk-1"}])
            raise AssertionError(f"Unexpected table: {self.table}")

    class FakeClient:
        def table(self, name):
            return Query(name)

    def embeddings_must_not_run(*args, **kwargs):
        raise AssertionError("The same CV must not consume embedding quota again.")

    monkeypatch.setattr(service, "embed_texts", embeddings_must_not_run)

    result = service._persist_prepared(
        {
            "cv": {"cv_hash": "same-hash", "filename": "CV.pdf"},
            "chunks": [{"text": "existing chunk"}],
        },
        client=FakeClient(),
        user_id="user-1",
    )

    assert result["cached"] is True
    assert result["cv_version_id"] == "cv-version-1"
    assert result["chunk_count"] == 1
