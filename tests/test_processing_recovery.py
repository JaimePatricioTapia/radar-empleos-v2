from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.search import processing


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.operation = "select"
        self.filters = {}
        self.in_filters = {}
        self.limit_value = None
        self.payload = None

    def select(self, *args):
        self.operation = "select"
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def gte(self, key, value):
        self.filters[f"gte:{key}"] = value
        return self

    def in_(self, key, values):
        self.in_filters[key] = set(values)
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def upsert(self, rows, on_conflict=None):
        self.operation = "upsert"
        self.payload = rows
        return self

    def execute(self):
        if self.table_name == "job_offers":
            if self.operation == "select":
                return SimpleNamespace(data=list(self.client.offers))
            return SimpleNamespace(data=[])

        if self.table_name != "job_chunks":
            raise AssertionError(f"Unexpected table {self.table_name}")

        if self.operation == "upsert":
            for row in self.payload:
                key = (row["job_offer_id"], row["chunk_index"])
                current = next(
                    (item for item in self.client.chunks
                     if (item["job_offer_id"], item["chunk_index"]) == key),
                    None,
                )
                if current:
                    current.update(row)
                else:
                    self.client.chunks.append({
                        **row,
                        "id": f"chunk-{len(self.client.chunks) + 1}",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
            return SimpleNamespace(data=list(self.payload))

        rows = list(self.client.chunks)
        for key, value in self.filters.items():
            if key.startswith("gte:"):
                field = key.split(":", 1)[1]
                rows = [row for row in rows if row.get(field, "") >= value]
            else:
                rows = [row for row in rows if row.get(key) == value]
        for key, values in self.in_filters.items():
            rows = [row for row in rows if row.get(key) in values]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, offer):
        self.offers = [offer]
        self.chunks = []

    def table(self, name):
        return FakeQuery(self, name)


def test_partial_embedding_batch_is_persisted_and_only_missing_chunks_retry(monkeypatch):
    offer = {
        "id": "offer-1",
        "title": "Business Analyst Minería",
        "company": "Minera",
        "description": "Responsabilidades y requisitos: " + ("gestión de proyectos mineros y análisis funcional. " * 55),
        "raw_metadata": {},
        "lifecycle_status": "NUEVA",
        "captured_at": "2026-11-23T10:00:00+00:00",
    }
    client = FakeClient(offer)
    monkeypatch.setattr(
        processing,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="fake",
            embedding_model="gemini-embedding-001",
            max_daily_job_chunks=250,
            max_daily_evaluations=15,
        ),
    )
    expected = processing.chunk_job_description(offer["title"], offer["description"])
    assert len(expected) >= 2

    calls = []

    def fake_embed_texts(texts, *, on_batch, **kwargs):
        calls.append(list(texts))
        if len(calls) == 1:
            on_batch(0, texts[:1], [[0.0] * 3072])
            raise RuntimeError("simulated interruption after first persisted sub-batch")
        vectors = [[0.0] * 3072 for _ in texts]
        on_batch(0, texts, vectors)
        return vectors

    monkeypatch.setattr(processing, "embed_texts", fake_embed_texts)

    with pytest.raises(RuntimeError, match="simulated interruption"):
        processing.build_job_chunks(client, user_id="user-1", limit=10)

    assert len(client.chunks) == 1
    saved_index = client.chunks[0]["chunk_index"]

    result = processing.build_job_chunks(client, user_id="user-1", limit=10)

    assert len(calls[0]) == len(expected)
    assert len(calls[1]) == len(expected) - 1
    assert client.chunks[0]["chunk_index"] == saved_index
    assert {row["chunk_index"] for row in client.chunks} == {
        int(chunk["chunk_index"]) for chunk in expected
    }
    assert result["offers_chunked"] == 1
