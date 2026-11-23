"""Ejecución de búsquedas fuera del hilo de Streamlit con sesión Auth aislada."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from supabase import create_client

from src.config import get_settings
from src.search.pipeline import run_full_search_pipeline


def _authenticated_worker_client(client: Any) -> Any:
    """Clona el cliente para el worker y propaga explícitamente el JWT del usuario.

    El cliente de Streamlit no se comparte entre hilos: el RPC vectorial depende
    de auth.uid(), y una sesión no propagada correctamente produce cero candidatos
    sin necesariamente generar un error HTTP.
    """
    auth = getattr(client, "auth", None)
    if auth is None:
        # Permite clientes falsos/simples usados en pruebas unitarias.
        return client
    response = auth.get_session()
    session = getattr(response, "session", None) or response
    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)
    if not access_token or not refresh_token:
        raise RuntimeError(
            "No se pudo obtener la sesión autenticada de Supabase para el proceso "
            "en segundo plano. Cierre sesión e ingrese nuevamente."
        )
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Falta la configuración pública de Supabase para el worker.")
    worker_client = create_client(settings.supabase_url, settings.supabase_key)
    worker_client.auth.set_session(access_token, refresh_token)
    return worker_client


@dataclass
class SearchTask:
    """Estado de una ejecución para que la interfaz la consulte sin bloquearse."""

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
        # Leer la sesión en el hilo de Streamlit y crear un cliente independiente.
        worker_client = _authenticated_worker_client(client)

        def emit_progress(event: dict) -> None:
            self.events.put({"type": "progress", "data": event})

        def emit_offer(offer: dict) -> None:
            self.events.put({"type": "offer", "data": offer})

        def emit_message(message: str) -> None:
            self.events.put({"type": "message", "data": message})

        def run() -> None:
            try:
                self.result = run_full_search_pipeline(
                    worker_client,
                    **kwargs,
                    progress=emit_message,
                    on_progress=emit_progress,
                    on_offer=emit_offer,
                    should_stop=self.stop_event.is_set,
                )
            except Exception as exc:  # el trabajo confirmado permanece en Supabase
                self.error = f"{type(exc).__name__}: {exc}"
            finally:
                self.finished = True
                self.events.put({"type": "finished"})

        self.thread = threading.Thread(target=run, name="radar-search", daemon=True)
        self.thread.start()
        return self


def start_search_task(client: Any, **kwargs) -> SearchTask:
    """Inicia búsqueda y procesamiento con una sesión autenticada aislada."""
    return SearchTask().start(client, **kwargs)
