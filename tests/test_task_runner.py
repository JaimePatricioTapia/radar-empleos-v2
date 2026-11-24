from unittest.mock import patch

from src.search.task_runner import SearchTask


def test_search_task_stop_signal_is_thread_safe_and_visible():
    task = SearchTask()
    task.request_stop()

    assert task.stop_event.is_set()
    assert task.stop_requested is True
    assert task.events.get_nowait()["type"] == "stop_requested"


def test_search_task_runs_pipeline_and_streams_events():
    task = SearchTask()

    def fake_pipeline(client, **kwargs):
        kwargs["progress"]("Etapa de prueba")
        kwargs["on_progress"]({"stage": "discovery", "queries_completed": 1})
        kwargs["on_offer"]({"title": "Business Analyst"})
        assert kwargs["should_stop"]() is False
        return {"completed": True}

    with patch("src.search.task_runner.run_full_search_pipeline", side_effect=fake_pipeline):
        task.start(object(), user_id="user-1")
        task.thread.join(timeout=2)

    assert task.finished is True
    assert task.error is None
    assert task.result == {"completed": True}
    event_types = []
    while not task.events.empty():
        event_types.append(task.events.get_nowait()["type"])
    assert event_types == ["message", "progress", "offer", "finished"]

def test_worker_uses_isolated_client_with_authenticated_user_jwt():
    from types import SimpleNamespace
    from src.search import task_runner

    session = SimpleNamespace(access_token="user-access-token", refresh_token="user-refresh-token")
    source_client = SimpleNamespace(auth=SimpleNamespace(
        get_session=lambda: SimpleNamespace(session=session)
    ))
    worker_client = SimpleNamespace(auth=SimpleNamespace(
        set_session=lambda access, refresh: (access, refresh)
    ))

    with (
        patch.object(task_runner, "get_settings", return_value=SimpleNamespace(
            supabase_url="https://example.supabase.co", supabase_key="publishable-key"
        )),
        patch.object(task_runner, "create_client", return_value=worker_client) as factory,
    ):
        result = task_runner._authenticated_worker_client(source_client)

    factory.assert_called_once_with("https://example.supabase.co", "publishable-key")
    assert result is worker_client
    assert worker_client.auth.set_session("user-access-token", "user-refresh-token") == (
        "user-access-token", "user-refresh-token"
    )


def test_worker_fails_fast_if_authenticated_session_is_missing():
    from types import SimpleNamespace
    from src.search.task_runner import _authenticated_worker_client

    client = SimpleNamespace(auth=SimpleNamespace(
        get_session=lambda: SimpleNamespace(session=None)
    ))
    import pytest
    with pytest.raises(RuntimeError, match="sesión autenticada"):
        _authenticated_worker_client(client)
