"""Orquestación de búsqueda multifuente y persistencia en Supabase."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Callable

from src.db.repository import upsert_job_offer
from src.search.sources import CONNECTORS, SOURCE_REGISTRY, canonical_job_url

logger = logging.getLogger(__name__)

DEFAULT_TARGET_ROLES = [
    "Business Analyst Minería",
    "Business Analyst Senior TI",
    "Analista de Negocio Minería",
    "Analista Funcional TI",
    "Analista Funcional Banca Digital",
    "Jefe de Proyectos TI",
    "Project Manager TI Minería",
    "PMO TI",
    "Transformación Digital Minería",
    "Analista de Procesos Minería",
    "Product Owner Banca Digital",
    "Product Owner IA",
    "Especialista Tecnología Operacional Minera",
]
DEFAULT_SOURCES = [
    "linkedin", "indeed", "chiletrabajos", "computrabajo",
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
    url = canonical_job_url(str(offer.get("source_url") or ""))
    identity = url or "|".join(str(offer.get(k) or "").strip().lower()
                               for k in ("title", "company", "location", "source"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _queries_for_source(source: str, roles: list[str]) -> list[tuple[str, str]]:
    """Reduce LinkedIn a una sola consulta booleana para evitar ráfagas repetidas."""
    if source == "linkedin":
        grouped = " OR ".join(f'"{role}"' for role in roles)
        return [(f"({grouped})", "cargos objetivo agrupados")]
    return [(role, role) for role in roles]


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
    planned_queries = sum(len(_queries_for_source(source, roles)) for source in sources)
    stats = {"queries": planned_queries, "total_found": 0, "saved": 0,
             "duplicates": 0, "errors": 0, "by_source": {}, "error_details": [], "offers": []}
    seen = set()
    for source in sources:
        label, connector_name = SOURCE_REGISTRY[source]
        connector = CONNECTORS[connector_name]
        source_stats = {"found": 0, "saved": 0, "duplicates": 0, "errors": 0}
        source_queries = _queries_for_source(source, roles)
        for query, query_label in source_queries:
            if progress:
                progress(f"Buscando «{query_label}» en {label}…")
            try:
                query_limit = (
                    max(limit_per_query, min(limit_per_query * len(roles), 25))
                    if source == "linkedin" else limit_per_query
                )
                offers = connector(query, limit=query_limit)
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
                    if not existing.data and offer.get("source_url"):
                        existing = (client.table("job_offers").select("id")
                                    .eq("user_id", user_id)
                                    .eq("source_url", offer["source_url"])
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
                detail = f"{label} / {query_label}: {type(exc).__name__}: {exc}"
                stats["error_details"].append(detail[:500])
                logger.exception("Falló búsqueda %s para %s", source, query_label)
        stats["by_source"][source] = source_stats
    return stats
