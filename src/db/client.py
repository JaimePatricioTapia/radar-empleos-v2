"""Fábrica de clientes Supabase aislados por sesión de Streamlit."""
from supabase import Client, create_client
from src.config import get_settings


def get_supabase_client() -> Client:
    """Crea un cliente nuevo; el llamador lo conserva en su session_state.

    No cachear globalmente: el cliente contiene el estado Auth del usuario.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError("Configura SUPABASE_URL y SUPABASE_KEY en los secretos de Streamlit o entorno local.")
    return create_client(settings.supabase_url, settings.supabase_key)
