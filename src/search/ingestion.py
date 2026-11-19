"""Orquestación de búsqueda multifuente y persistencia en Supabase."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Callable

from src.db.repository import upsert_job_offer
from src.search.sources import CONNECTORS, SOURCE_REGISTRY

logger = logging.getLogger(__name__)

DEFAULT_TARGET_ROLES = [
    "Business Analyst Minería", "Analista Funcional Minería",
    "Project Manager TI Minería", "Transformación Digital Minería",
    "Coordinador Proyectos Tecnológicos Minería", "Especialista TI Minería",
    "Ingeniero de Datos Minería", "Senior Business Analyst",
    "IT Project Manager", "Analista de Procesos",
    "Consultor de Automatización", "Especialista en IA y Datos",
    "Business Process Consultant",
]
DEFAULT_SOURCES = [
    "linkedin", "indeed", "google", "chiletrabajos", "computrabajo",
    "contutalento", "bne", "codelco", "finning", "getonbrd",
]


def _parse_published_at(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _stable_hash(offer: dict) -> str:
    url = str(offer.get("source_url") or "").split("?")[0].rstrip("/").lower()
    identity = url or "|".join(str(offer.get(k) or "").strip().lower()
                               for k in ("title", "company", "location", "source"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def run_discovery(client, *, user_id: str, roles: list[str], sources: list[str],
                  limit_per_query: int = 12,
                  progress: Callable[[str], None] | None = None) -> dict:
    """Descubre y guarda avisos sin evaluar con Gemini."""
    roles = [re.sub(r"\s+", " ", role).strip() for role in roles if role.strip()]
    sources = list(dict.fromkeys(sources))
    unknown = sorted(set(sources) - set(SOURCE_REGISTRY))
    if unknown:
        raise ValueError(f"Fuentes no reconocidas: {', '.join(unknown)}")
    if not roles or not sources:
        raise ValueError("Seleccione al menos un cargo y un portal.")
    limit_per_query = max(1, min(int(limit_per_query), 30))
    stats = {"queries": len(roles) * len(sources), "total_found": 0, "saved": 0,
             "duplicates": 0, "errors": 0, "by_source": {}, "error_details": [], "offers": []}
    seen = set()
    for source in sources:
        label, connector_name = SOURCE_REGISTRY[source]
        connector = CONNECTORS[connector_name]
        source_stats = {"found": 0, "saved": 0, "duplicates": 0, "errors": 0}
        for role in roles:
            if progress:
                progress(f"Buscando «{role}» en {label}…")
            try:
                offers = connector(role, limit=limit_per_query)
                for offer in offers:
                    if not offer:
                        continue
                    stats["total_found"] += 1
                    source_stats["found"] += 1
                    offer["job_hash"] = _stable_hash(offer)
                    offer["published_at"] = _parse_published_at(offer.get("published_at"))
                    key = offer["job_hash"]
                    if key in seen:
                        stats["duplicates"] += 1
                        source_stats["duplicates"] += 1
                        continue
                    seen.add(key)
                    existing = (client.table("job_offers").select("id")
                                .eq("user_id", user_id).eq("job_hash", key)
                                .limit(1).execute())
                    if existing.data:
                        stats["duplicates"] += 1
                        source_stats["duplicates"] += 1
                        continue
                    row = upsert_job_offer(client, user_id=user_id, offer=offer)
                    stats["saved"] += 1
                    source_stats["saved"] += 1
                    stats["offers"].append({
                        "id": row["id"], "title": row["title"], "company": row.get("company"),
                        "location": row.get("location"), "source": row.get("source"),
                        "source_url": row.get("source_url"), "published_at": row.get("published_at"),
                    })
            except Exception as exc:
                stats["errors"] += 1
                source_stats["errors"] += 1
                detail = f"{label} / {role}: {type(exc).__name__}: {exc}"
                stats["error_details"].append(detail[:500])
                logger.exception("Falló búsqueda %s para %s", source, role)
        stats["by_source"][source] = source_stats
    return stats
