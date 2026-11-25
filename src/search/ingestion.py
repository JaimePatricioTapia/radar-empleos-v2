"""Orquestación de búsqueda multifuente y persistencia en Supabase."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable

from src.db.repository import upsert_job_offer
from src.search.sources import CONNECTORS, SOURCE_REGISTRY, canonical_job_url, search_custom_portal
from src.search.relevance import assess_offer_relevance

logger = logging.getLogger(__name__)
MAX_PUBLICATION_AGE_DAYS = 14
MAX_CONSECUTIVE_SOURCE_ERRORS = 2

DEFAULT_TARGET_FUNCTIONS = [
    "Levantamiento y análisis de requerimientos",
    "Gestión y seguimiento de proyectos TI",
    "Control y seguimiento de KPI",
    "Mejora continua y optimización de procesos",
    "Gestión de riesgos tecnológicos y ciberseguridad",
    "Implementación y actualización de sistemas",
    "Continuidad operacional y coordinación de operaciones",
    "Gestión de proveedores y contratos",
    "Análisis de datos y elaboración de reportes",
    "Transformación digital y automatización",
    "Gestión de backlog y priorización de requerimientos",
]


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
    "linkedin", "indeed", "glassdoor", "chiletrabajos", "computrabajo",
    "contutalento", "bne", "codelco", "finning", "getonbrd",
]


def _parse_published_at(value, *, now: datetime | None = None):
    """Normaliza fechas ISO, calendario y expresiones relativas ES/EN sin inventar fechas."""
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            dt = None
            lowered = raw.lower()
            if lowered in {"hoy", "today"}:
                dt = now
            elif lowered in {"ayer", "yesterday"}:
                dt = now - timedelta(days=1)
            else:
                relative = re.search(
                    r"(?:hace\s*)?(\d+)\s*(minutos?|minutes?|d[ií]as?|days?|hours?|horas?|weeks?|semanas?|mes(?:es)?|months?|a[nñ]os?|years?)\s*(?:atr[aá]s|ago)?",
                    lowered,
                )
                if relative:
                    amount = int(relative.group(1))
                    unit = relative.group(2)
                    if unit.startswith(("m", "minut")) and unit not in {"mes", "meses", "month", "months"}:
                        dt = now - timedelta(minutes=amount)
                    elif unit.startswith(("h", "hora")):
                        dt = now - timedelta(hours=amount)
                    elif unit.startswith(("w", "semana")):
                        dt = now - timedelta(weeks=amount)
                    elif unit.startswith(("mes", "month")):
                        dt = now - timedelta(days=30 * amount)
                    elif unit.startswith(("año", "ano", "year")):
                        dt = now - timedelta(days=365 * amount)
                    else:
                        dt = now - timedelta(days=amount)
                else:
                    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
                        try:
                            dt = datetime.strptime(raw, fmt)
                            break
                        except ValueError:
                            continue
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _stable_hash(offer: dict) -> str:
    url = canonical_job_url(str(offer.get("source_url") or ""))
    identity = url or "|".join(str(offer.get(k) or "").strip().lower()
                               for k in ("title", "company", "location", "source"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _queries_for_source(source: str, roles: list[str], functions: list[str] | None = None) -> list[tuple[str, str]]:
    """Combina cargos y funciones; LinkedIn conserva una única consulta agrupada."""
    terms = list(dict.fromkeys([*roles, *(functions or [])]))
    if source == "linkedin":
        grouped = " OR ".join(f'"{term}"' for term in terms)
        return [(f"({grouped})", "cargos y funciones agrupados")]
    return [(term, term) for term in terms]


def run_discovery(client, *, user_id: str, roles: list[str], sources: list[str],
                  functions: list[str] | None = None,
                  limit_per_query: int = 12,
                  progress: Callable[[str], None] | None = None,
                  on_progress: Callable[[dict], None] | None = None,
                  on_offer: Callable[[dict], None] | None = None,
                  role_context: list[dict] | None = None,
                  custom_sources: list[dict] | None = None,
                  should_stop: Callable[[], bool] | None = None,
                  max_age_days: int = MAX_PUBLICATION_AGE_DAYS) -> dict:
    """Descubre y guarda avisos sin evaluar con Gemini."""
    roles = [re.sub(r"\s+", " ", role).strip() for role in roles if role and role.strip()]
    functions = [re.sub(r"\s+", " ", item).strip() for item in (functions or []) if item and item.strip()]
    search_terms = list(dict.fromkeys([*roles, *functions]))
    sources = list(dict.fromkeys(sources))
    custom_by_id = {
        str(item.get("id")): item for item in (custom_sources or [])
        if item.get("id") and item.get("url_template")
    }
    unknown = sorted(set(sources) - set(SOURCE_REGISTRY) - set(custom_by_id))
    if unknown:
        raise ValueError(f"Fuentes no reconocidas: {', '.join(unknown)}")
    if not search_terms or not sources:
        raise ValueError("Seleccione al menos un cargo o función y un portal.")
    limit_per_query = max(1, min(int(limit_per_query), 30))
    planned_queries = sum(len(_queries_for_source(source, roles, functions)) for source in sources)
    stats = {"queries": planned_queries, "queries_completed": 0, "queries_skipped": 0, "stopped_early": False,
             "total_found": 0, "saved": 0, "duplicates": 0, "stale_skipped": 0,
             "irrelevant_skipped": 0, "filtered_examples": [],
             "publication_date_unknown": 0, "errors": 0, "by_source": {},
             "error_details": [], "offers": []}
    started_at = datetime.now(timezone.utc)
    role_lookup = {}
    for family in role_context or []:
        for title in family.get("titles", []):
            role_lookup[re.sub(r"\s+", " ", str(title)).strip().casefold()] = family

    def notify(event: dict) -> None:
        if on_progress:
            event["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            on_progress(event)

    seen = set()
    for source in sources:
        if source in custom_by_id:
            portal = custom_by_id[source]
            label = str(portal.get("name") or "Portal personalizado")
            connector = lambda query, limit=limit_per_query, portal=portal: search_custom_portal(
                query, portal=portal, limit=limit
            )
        else:
            label, connector_name = SOURCE_REGISTRY[source]
            connector = CONNECTORS[connector_name]
        source_stats = {"found": 0, "saved": 0, "duplicates": 0, "irrelevant_skipped": 0, "errors": 0}
        source_queries = _queries_for_source(source, roles, functions)
        consecutive_errors = 0
        for query_index, (query, query_label) in enumerate(source_queries):
            if should_stop and should_stop():
                stats["stopped_early"] = True
                break
            if consecutive_errors >= MAX_CONSECUTIVE_SOURCE_ERRORS:
                skipped = len(source_queries) - query_index
                stats["queries_skipped"] += skipped
                source_stats["skipped_queries"] = skipped
                if progress:
                    progress(f"Se omiten {skipped} consultas restantes de {label} tras {consecutive_errors} errores consecutivos.")
                if on_progress:
                    notify({
                        "stage": "discovery", "status": "source_skipped",
                        "source": source, "source_label": label,
                        "queries_completed": stats["queries_completed"],
                        "queries_skipped": stats["queries_skipped"],
                        "queries_total": planned_queries,
                        "offers_found": stats["total_found"], "offers_saved": stats["saved"],
                        "duplicates": stats["duplicates"], "irrelevant_skipped": stats["irrelevant_skipped"],
                        "errors": stats["errors"],
                        "elapsed_seconds": int((datetime.now(timezone.utc)-started_at).total_seconds()),
                    })
                break
            family_for_query = role_lookup.get(str(query_label).strip().casefold())
            if family_for_query:
                display_query_label = f"{family_for_query.get('family_name')} · {query_label}"
            elif source == "linkedin" and role_context:
                family_names = ", ".join(item.get("family_name", "") for item in role_context)
                display_query_label = f"Familias agrupadas: {family_names}"
            else:
                display_query_label = query_label
            if progress:
                progress(f"Buscando «{display_query_label}» en {label}…")
            if on_progress:
                notify({
                    "stage": "discovery", "status": "running", "source": source,
                    "source_label": label, "query": display_query_label,
                    "queries_completed": stats["queries_completed"],
                    "queries_total": planned_queries, "offers_found": stats["total_found"],
                    "offers_saved": stats["saved"], "duplicates": stats["duplicates"],
                    "errors": stats["errors"], "elapsed_seconds": int((datetime.now(timezone.utc)-started_at).total_seconds()),
                })
            try:
                query_limit = (
                    max(limit_per_query, min(limit_per_query * len(search_terms), 25))
                    if source == "linkedin" else limit_per_query
                )
                # Consultar cada cargo o función tal como está definido.
                # Agregar términos de dominio con AND implícito estrechaba
                # demasiado la búsqueda y excluía ofertas equivalentes.
                connector_query = query
                offers = connector(connector_query, limit=query_limit)
                consecutive_errors = 0
                for offer in offers:
                    if not offer:
                        continue
                    stats["total_found"] += 1
                    source_stats["found"] += 1
                    is_relevant, relevance_reason = assess_offer_relevance(offer)
                    if not is_relevant:
                        stats["irrelevant_skipped"] += 1
                        source_stats["irrelevant_skipped"] += 1
                        if len(stats["filtered_examples"]) < 12:
                            stats["filtered_examples"].append({
                                "title": str(offer.get("title") or "Sin título")[:180],
                                "source": source,
                                "reason": relevance_reason,
                            })
                        continue
                    offer["job_hash"] = _stable_hash(offer)
                    # Procedencia auditable de la consulta, almacenada en JSON existente.
                    if source == "linkedin":
                        matched_families = list(role_context or [])
                    else:
                        family = role_lookup.get(str(query_label).strip().casefold())
                        matched_families = [family] if family else []
                    metadata = dict(offer.get("raw_metadata") or {})
                    metadata["search_origin"] = {
                        "families": [
                            {"id": item.get("family_id"), "name": item.get("family_name"),
                             "priority": item.get("priority")}
                            for item in matched_families
                        ],
                        "query": query_label,
                        "query_type": "funcion" if query_label in functions else ("cargo_y_funcion" if source == "linkedin" and functions else "cargo"),
                        "domain_terms": (family_for_query or {}).get("domain_terms", []) if source != "linkedin" else [],
                    }
                    offer["raw_metadata"] = metadata
                    published = _parse_published_at(offer.get("published_at"))
                    offer["published_at"] = published
                    if published:
                        age = datetime.now(timezone.utc) - datetime.fromisoformat(published)
                        if age > timedelta(days=max(1, int(max_age_days))):
                            stats["stale_skipped"] += 1
                            source_stats.setdefault("stale_skipped", 0)
                            source_stats["stale_skipped"] += 1
                            continue
                        offer.setdefault("raw_metadata", {})["publication_date_status"] = "verified_recent"
                    else:
                        stats["publication_date_unknown"] += 1
                        source_stats.setdefault("publication_date_unknown", 0)
                        source_stats["publication_date_unknown"] += 1
                        offer.setdefault("raw_metadata", {})["publication_date_status"] = "unknown"
                    key = offer["job_hash"]
                    if key in seen:
                        stats["duplicates"] += 1
                        source_stats["duplicates"] += 1
                        continue
                    seen.add(key)
                    existing = (client.table("job_offers").select("id,published_at,raw_metadata")
                                .eq("user_id", user_id).eq("job_hash", key)
                                .limit(1).execute())
                    if not existing.data and offer.get("source_url"):
                        existing = (client.table("job_offers").select("id")
                                    .eq("user_id", user_id)
                                    .eq("source_url", offer["source_url"])
                                    .limit(1).execute())
                    if existing.data:
                        previous_offer = existing.data[0]
                        if published and not previous_offer.get("published_at"):
                            previous_metadata = previous_offer.get("raw_metadata") or {}
                            client.table("job_offers").update({
                                "published_at": published,
                                "raw_metadata": {
                                    **previous_metadata,
                                    "publication_date_status": "verified_recent",
                                },
                            }).eq("id", previous_offer["id"]).eq("user_id", user_id).execute()
                        stats["duplicates"] += 1
                        source_stats["duplicates"] += 1
                        continue
                    row = upsert_job_offer(client, user_id=user_id, offer=offer)
                    stats["saved"] += 1
                    source_stats["saved"] += 1
                    saved_offer = {
                        "id": row["id"], "title": row["title"], "company": row.get("company"),
                        "location": row.get("location"), "source": row.get("source"),
                        "source_url": row.get("source_url"), "published_at": row.get("published_at"),
                        "publication_date_status": (offer.get("raw_metadata") or {}).get("publication_date_status", "unknown"),
                    }
                    stats["offers"].append(saved_offer)
                    if on_offer:
                        on_offer(saved_offer)
            except Exception as exc:
                stats["errors"] += 1
                source_stats["errors"] += 1
                consecutive_errors += 1
                detail = f"{label} / {query_label}: {type(exc).__name__}: {exc}"
                stats["error_details"].append(detail[:500])
                logger.exception("Falló búsqueda %s para %s", source, query_label)
            finally:
                stats["queries_completed"] += 1
                if on_progress:
                    notify({
                        "stage": "discovery", "status": "stopped" if stats["stopped_early"] else "running",
                        "source": source, "source_label": label, "query": display_query_label,
                        "queries_completed": stats["queries_completed"], "queries_skipped": stats["queries_skipped"],
                        "queries_total": planned_queries,
                        "offers_found": stats["total_found"], "offers_saved": stats["saved"],
                        "duplicates": stats["duplicates"], "stale_skipped": stats["stale_skipped"],
                        "irrelevant_skipped": stats["irrelevant_skipped"],
                        "publication_date_unknown": stats["publication_date_unknown"],
                        "errors": stats["errors"],
                        "elapsed_seconds": int((datetime.now(timezone.utc)-started_at).total_seconds()),
                    })
            if should_stop and should_stop():
                stats["stopped_early"] = True
            if stats["stopped_early"]:
                break
        stats["by_source"][source] = source_stats
        if stats["stopped_early"]:
            break
    return stats
