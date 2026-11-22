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
