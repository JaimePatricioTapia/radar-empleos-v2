"""Persistencia de preferencias de búsqueda privadas por usuario."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def load_search_preferences(client: Any, *, user_id: str) -> dict:
    """Carga portales y términos habilitados del usuario autenticado."""
    portals = (
        client.table("user_search_portals").select("*")
        .eq("user_id", user_id).order("created_at").execute().data or []
    )
    terms = (
        client.table("user_search_terms").select("*")
        .eq("user_id", user_id).order("created_at").execute().data or []
    )
    return {"portals": portals, "terms": terms}


def save_search_portal(client: Any, *, user_id: str, name: str, url_template: str) -> dict:
    name = " ".join(str(name).split())[:80]
    url_template = str(url_template).strip()[:1000]
    if not name:
        raise ValueError("Ingrese el nombre del portal.")
    if not url_template.startswith(("https://", "http://")):
        raise ValueError("La URL debe comenzar con http:// o https://.")
    existing = (
        client.table("user_search_portals").select("*")
        .eq("user_id", user_id).eq("url_template", url_template).limit(1).execute().data or []
    )
    if existing:
        return existing[0]
    response = client.table("user_search_portals").insert({
        "user_id": user_id, "name": name, "url_template": url_template, "enabled": True,
    }).execute()
    if not response.data:
        raise RuntimeError("Supabase no confirmó el guardado del portal.")
    return response.data[0]


def set_search_portal_enabled(client: Any, *, user_id: str, portal_id: str, enabled: bool) -> None:
    client.table("user_search_portals").update({
        "enabled": bool(enabled), "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", portal_id).eq("user_id", user_id).execute()


def delete_search_portal(client: Any, *, user_id: str, portal_id: str) -> None:
    client.table("user_search_portals").delete().eq("id", portal_id).eq("user_id", user_id).execute()


def save_search_terms(
    client: Any, *, user_id: str, term_type: str, terms: list[str]
) -> list[str]:
    """Guarda términos personalizados sin duplicar diferencias de mayúsculas/espacios."""
    if term_type not in {"cargo", "funcion"}:
        raise ValueError("Tipo de término no permitido.")
    existing = (
        client.table("user_search_terms").select("term")
        .eq("user_id", user_id).eq("term_type", term_type).execute().data or []
    )
    known = {" ".join(str(row["term"]).split()).casefold() for row in existing}
    inserted = []
    for raw in terms:
        term = " ".join(str(raw).split())
        normalized = term.casefold()
        if len(term) < 2 or len(term) > 160 or normalized in known:
            continue
        response = client.table("user_search_terms").insert({
            "user_id": user_id, "term_type": term_type, "term": term, "enabled": True,
        }).execute()
        if response.data:
            inserted.append(term)
            known.add(normalized)
    return inserted


def delete_search_term(client: Any, *, user_id: str, term_id: str) -> None:
    client.table("user_search_terms").delete().eq("id", term_id).eq("user_id", user_id).execute()
