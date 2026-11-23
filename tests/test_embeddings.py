from types import SimpleNamespace

import pytest

from src.cv import embeddings
from src.cv.embeddings import embed_texts


def test_embeddings_reject_empty_text():
    with pytest.raises(ValueError, match="vacíos"):
        embed_texts([""], api_key="fake")


def test_embeddings_fix_dimensions():
    with pytest.raises(ValueError, match="3.072"):
        embed_texts(["texto"], api_key="fake", output_dimensionality=768)


def test_retry_delay_uses_google_retry_after():
    error = RuntimeError("429 RESOURCE_EXHAUSTED retry in 25.688501255s")
    assert embeddings._retry_delay_seconds(error, 0) == pytest.approx(25.688501255)


def test_embeddings_retry_429_and_persist_each_batch(monkeypatch):
    calls = []
    sleeps = []
    persisted = []

    class FakeModels:
        def embed_content(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED retry in 0.25s")
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.0] * 3072)]
            )

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)
    monkeypatch.setattr(embeddings.time, "sleep", sleeps.append)

    vectors = embed_texts(
        ["primer texto", "segundo texto"],
        api_key="fake",
        batch_size=1,
        on_batch=lambda start, texts, batch_vectors: persisted.append(
            (start, list(texts), len(batch_vectors))
        ),
    )

    assert len(vectors) == 2
    assert len(calls) == 3
    assert sleeps == [0.25]
    assert persisted == [
        (0, ["primer texto"], 1),
        (1, ["segundo texto"], 1),
    ]


def test_embeddings_do_not_retry_non_transient_errors(monkeypatch):
    sleeps = []

    class FakeModels:
        def embed_content(self, **kwargs):
            raise ValueError("invalid model name")

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)
    monkeypatch.setattr(embeddings.time, "sleep", sleeps.append)

    with pytest.raises(ValueError, match="invalid model"):
        embed_texts(["texto"], api_key="fake")

    assert sleeps == []



def test_embedding_rate_limit_exhaustion_raises_resumable_error(monkeypatch):
    calls = []
    waits = []

    class FakeModels:
        def embed_content(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("429 RESOURCE_EXHAUSTED retry in 0.5s")

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(embeddings.genai, "Client", FakeClient)
    monkeypatch.setattr(embeddings.time, "sleep", waits.append)

    with pytest.raises(embeddings.EmbeddingRateLimitError) as error:
        embed_texts(["texto"], api_key="fake", max_retries=1)

    assert len(calls) == 2
    assert waits == [0.5]
    assert error.value.retry_after_seconds == pytest.approx(0.5)
