"""Ejecución de búsquedas fuera del hilo de Streamlit con eventos y parada segura."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.search.pipeline import run_full_search_pipeline


@dataclass
class SearchTask:
    """Estado de una ejecución para que la interfaz pueda consultarla sin bloquearse."""

    events: queue.Queue = field(default_factory=queue.Queue)
    stop_event: threading.Event = field(default_factory=threading.Event)
    result: dict | None = None
    error: str | None = None
    finished: bool = False
    stop_requested: bool = False
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    thread: threading.Thread | None = None

    def request_stop(self) -> None:
        self.stop_requested = True
        self.stop_event.set()
        self.events.put({"type": "stop_requested"})

    def start(self, client: Any, **kwargs) -> "SearchTask":
        def emit_progress(event: dict) -> None:
            self.events.put({"type": "progress", "data": event})

        def emit_offer(offer: dict) -> None:
            self.events.put({"type": "offer", "data": offer})

        def emit_message(message: str) -> None:
            self.events.put({"type": "message", "data": message})

        def run() -> None:
            try:
                self.result = run_full_search_pipeline(
                    client,
                    **kwargs,
                    progress=emit_message,
                    on_progress=emit_progress,
                    on_offer=emit_offer,
                    should_stop=self.stop_event.is_set,
                )
            except Exception as exc:  # surfaced in the UI; persisted work remains in Supabase
                self.error = f"{type(exc).__name__}: {exc}"
            finally:
                self.finished = True
                self.events.put({"type": "finished"})

        self.thread = threading.Thread(target=run, name="radar-search", daemon=True)
        self.thread.start()
        return self


def start_search_task(client: Any, **kwargs) -> SearchTask:
    """Inicia búsqueda y procesamiento en segundo plano sin bloquear la sesión."""
    return SearchTask().start(client, **kwargs)
