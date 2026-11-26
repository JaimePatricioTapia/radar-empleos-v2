from types import SimpleNamespace

from src.db import client as db_client


def test_supabase_client_is_created_per_call(monkeypatch):
    monkeypatch.setattr(
        db_client,
        "get_settings",
        lambda: SimpleNamespace(
            supabase_url="https://example.supabase.co",
            supabase_key="publishable-test-key",
        ),
    )
    created = []

    def fake_create_client(url, key):
        item = object()
        created.append((url, key, item))
        return item

    monkeypatch.setattr(db_client, "create_client", fake_create_client)

    first = db_client.get_supabase_client()
    second = db_client.get_supabase_client()

    assert first is not second
    assert len(created) == 2
    assert all(row[0] == "https://example.supabase.co" for row in created)
    assert all(row[1] == "publishable-test-key" for row in created)


def test_supabase_client_rejects_missing_secrets(monkeypatch):
    monkeypatch.setattr(
        db_client,
        "get_settings",
        lambda: SimpleNamespace(supabase_url=None, supabase_key=None),
    )
    try:
        db_client.get_supabase_client()
    except ValueError as exc:
        assert "SUPABASE_URL" in str(exc)
    else:
        raise AssertionError("Expected missing Supabase configuration to fail")
