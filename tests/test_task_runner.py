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
