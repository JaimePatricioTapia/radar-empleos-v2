"""Pipeline económico: Job Chunks -> embeddings -> ranking vectorial -> Gemini."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from src.config import get_settings
from src.cv.embeddings import embed_texts
from src.db.repository import save_evaluation
from src.evaluation.evaluator import evaluate_offer, GeminiEvaluationDeferred
from src.search.job_chunker import chunk_job_description
from src.search.salary import analyse_salary, attractiveness_score

logger = logging.getLogger(__name__)

MINIMUM_AFFINITY_SCORE = 85
# Puntaje 70–84: revisión humana, no descarte automático. Umbrales provisionales.
MANUAL_REVIEW_MINIMUM_SCORE = 70
# Topes operativos temporales para medir la cuota real de Gemini; configurables en src/config.py.
MAX_DAILY_JOB_CHUNKS = 1000
MAX_DAILY_EVALUATIONS = 100
CV_EVIDENCE_MATCH_COUNT = 8
MAX_EVALUATION_DESCRIPTION_CHARS = 10000
ROLLING_BUDGET_HOURS = 24

SECTOR_WEIGHTS = {
    "MINERIA": 100,
    "PROVEEDOR_MINERO": 92,
    "TECNOLOGIA_CONSULTORIA": 62,
    "BANCA_FINANZAS": 52,
    "OTROS": 30,
}
# Exclusiones determinísticas para evitar gastar embeddings/Gemini en roles
# que no corresponden a la trayectoria ni a los objetivos actuales.
EXCLUDED_ROLE_TERMS = (
    "scrum master", "practica", "practica profesional", "practicante", "internship",
    "trainee", "prevencionista", "higiene ocupacional",
)
EXCLUDED_COMPANIES = ("banco santander", "santander chile")
HEALTH_TERMS = ("isapre", "clínica", "clinica", "hospital", "centro médico", "centro medico")

TARGET_STRATEGY = {
    "target_roles": [
        "Business Analyst", "Analista de Negocio", "Analista Funcional",
        "Product Owner", "Product Manager digital", "IT Project Manager",
        "PMO", "Jefe o Coordinador de Proyectos TI",
        "Transformación Digital", "Procesos y Automatización",
        "Tecnología y Datos aplicados a Minería",
        "Operaciones y Sistemas Mineros",
    ],
    "priority_industries": [
        "Minería", "Proveedores y servicios mineros",
        "Tecnología y consultoría", "Banca y servicios financieros",
    ],
    "target_functions": [
        "Análisis de negocio y levantamiento funcional",
        "Implementación y mejora de sistemas",
        "Gestión de proyectos tecnológicos",
        "Transformación digital y optimización de procesos",
        "Tecnología aplicada a operaciones mineras",
        "Productos y canales digitales",
    ],
    "avoid_roles": [
        "Scrum Master", "Prevencionista de Riesgos",
        "Higiene Ocupacional", "Prácticas profesionales",
        "Internship", "Trainee",
    ],
    "location_preferences": (
        "Santiago y Región Metropolitana; otras regiones cuando el cargo "
        "sea por turnos; modalidad remota aceptable."
    ),
}


def _normalize_text(value: str) -> str:
    """Normaliza tildes y mayúsculas para clasificar texto en español."""
    import unicodedata
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def classify_sector(offer: dict) -> str:
    title = _normalize_text(offer.get("title") or "")
    company = _normalize_text(offer.get("company") or "")
    description = _normalize_text((offer.get("description") or "")[:5000])
    text = f"{title} {company} {description}"

    mining_terms = (
        "mineria", "minera", "minero", "codelco", "bhp", "escondida",
        "collahuasi", "sqm", "teck", "antofagasta minerals", "chuquicamata",
        "el teniente", "faena minera", "rajo", "subterranea", "raise boring",
        "concentradora", "relaves", "operaciones mina", "operacion minera",
        "equipos mina", "flota minera",
    )
    supplier_terms = (
        "proveedor", "contratista", "servicios mineros", "equipos mineros",
        "perforacion", "maquinaria minera", "finning", "master drilling",
        "komatsu", "echeverria izquierdo", "sandvik", "epiroc", "metso",
        "hexagon", "rpmglobal", "hexagon mining",
    )
    bank_terms = ("banco", "banca", "financiero", "financiera", "fintech",
                  "seguros", "medios de pago", "inversiones")
    tech_terms = ("consultoria", "tecnologia", "software", "transformacion digital", "sistemas")

    mining_context = any(term in text for term in mining_terms)
    supplier_context = any(term in text for term in supplier_terms)
    if mining_context and supplier_context:
        return "PROVEEDOR_MINERO"
    if mining_context:
        return "MINERIA"
    if any(term in company or term in title for term in bank_terms):
        return "BANCA_FINANZAS"
    if any(term in text for term in tech_terms):
        return "TECNOLOGIA_CONSULTORIA"
    return "OTROS"


def _excluded_reason(offer: dict) -> str | None:
    title = _normalize_text(offer.get("title") or "")
    company = _normalize_text(offer.get("company") or "")
    if any(_normalize_text(term) in title for term in EXCLUDED_ROLE_TERMS):
        return "Cargo fuera de los objetivos actuales (Scrum Master, práctica o prevención de riesgos)."
    if any(_normalize_text(term) in company for term in EXCLUDED_COMPANIES):
        return "Empresa excluida de las preferencias actuales."
    if any(_normalize_text(term) in f"{title} {company}" for term in HEALTH_TERMS):
        return "Sector salud fuera de las preferencias actuales."
    return None


def meets_affinity_threshold(score: int | None) -> bool:
    """Solo una afinidad laboral evaluada >=85 puede ser recomendada."""
    return score is not None and int(score) >= MINIMUM_AFFINITY_SCORE


def _priority_score(affinity: int, sector: str) -> int:
    """Prioridad estratégica informativa; nunca reemplaza el filtro de afinidad."""
    sector_weight = SECTOR_WEIGHTS.get(sector, 30)
    return max(0, min(100, int(0.75 * affinity + 0.25 * sector_weight + 0.5)))


def _rolling_budget_start() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=ROLLING_BUDGET_HOURS)).isoformat()


def _daily_chunk_usage(client: Any, *, user_id: str, daily_limit: int | None = None) -> int:
    limit = max(1, int(daily_limit or get_settings().max_daily_job_chunks))
    rows = (client.table("job_chunks").select("id").eq("user_id", user_id)
            .gte("created_at", _rolling_budget_start())
            .limit(limit).execute().data or [])
    return len(rows)


def _local_relevance_score(offer: dict) -> int:
    """Preselección gratuita y explicable; solo ordena, no descarta por afinidad."""
    title = _normalize_text(offer.get("title") or "")
    company = _normalize_text(offer.get("company") or "")
    description = _normalize_text((offer.get("description") or "")[:5000])
    score = 0
    title_terms = (
        "business analyst", "analista de negocio", "analista funcional",
        "project manager", "jefe de proyectos", "gerente de proyectos",
        "pmo", "transformacion digital", "product owner", "product manager",
        "analista de procesos", "especialista tecnologia", "sistemas mineros",
    )
    for term in title_terms:
        if term in title:
            score += 8
    mining_terms = ("mineria", "minera", "minero", "codelco", "bhp", "escondida",
                    "collahuasi", "sqm", "teck", "finning", "master drilling",
                    "antofagasta minerals", "raise boring")
    if any(term in f"{title} {company}" for term in mining_terms):
        score += 8
    if any(term in description for term in mining_terms):
        score += 3
    if any(term in description for term in ("levantamiento de requisitos", "procesos",
                                               "transformacion digital", "sistemas",
                                               "gestion de proyectos", "analisis funcional")):
        score += 3
    if any(term in f"{title} {description}" for term in ("sql", "power bi", "sap", "jira", "datos")):
        score += 1
    return score


def build_job_chunks(
    client: Any, *, user_id: str, limit: int = 100,
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Prepara ofertas prioritarias y persiste cada sublote apenas se calcula."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en .env.")

    daily_chunk_limit = max(1, int(settings.max_daily_job_chunks))
    used_today = _daily_chunk_usage(client, user_id=user_id, daily_limit=daily_chunk_limit)
    budget_remaining = max(0, daily_chunk_limit - used_today)
    offers = (client.table("job_offers")
              .select("id,title,company,description,raw_metadata,lifecycle_status,captured_at")
              .eq("user_id", user_id).eq("lifecycle_status", "NUEVA")
              .order("captured_at", desc=True).limit(1000).execute().data or [])
    empty = {
        "offers_seen": len(offers), "offers_chunked": 0, "chunks_saved": 0,
        "insufficient": 0, "excluded": 0, "eligible_pending": 0,
        "budget_exhausted": budget_remaining == 0,
        "budget_remaining": budget_remaining, "chunks_embedded_last_24h": used_today,
    }
    if not offers:
        return empty

    offer_ids = [item["id"] for item in offers]
    existing_rows = []
    for start in range(0, len(offer_ids), 100):
        existing_rows.extend(
            client.table("job_chunks").select("job_offer_id,chunk_index")
            .eq("user_id", user_id).in_("job_offer_id", offer_ids[start:start + 100])
            .execute().data or []
        )
    existing_by_offer: dict[str, set[int]] = {}
    for row in existing_rows:
        existing_by_offer.setdefault(row["job_offer_id"], set()).add(int(row["chunk_index"]))

    eligible: list[tuple[dict, list[dict]]] = []
    insufficient = 0
    excluded = 0
    for offer in offers:
        metadata = offer.get("raw_metadata") or {}
        if metadata.get("evaluation_filter"):
            excluded += 1
            continue
        reason = _excluded_reason(offer)
        if reason:
            client.table("job_offers").update({
                "sector_category": classify_sector(offer),
                "raw_metadata": {**metadata, "evaluation_filter": reason}
            }).eq("id", offer["id"]).eq("user_id", user_id).execute()
            excluded += 1
            continue
        description = (offer.get("description") or "").strip()
        if len(description) < 150:
            insufficient += 1
            if metadata.get("processing", {}).get("status") != "needs_description":
                client.table("job_offers").update({
                    "raw_metadata": {**metadata, "processing": {
                        "status": "needs_description",
                        "reason": "Descripción insuficiente para evaluación fiable."
                    }}
                }).eq("id", offer["id"]).eq("user_id", user_id).execute()
            continue
        chunks = chunk_job_description(offer["title"], description)
        present = existing_by_offer.get(offer["id"], set())
        missing = [chunk for chunk in chunks if int(chunk["chunk_index"]) not in present]
        if missing:
            eligible.append((offer, missing))

    # Priorizar localmente cargos y contexto minero; no se descartan ofertas por esta puntuación.
    eligible.sort(key=lambda item: (_local_relevance_score(item[0]), item[0].get("captured_at") or ""), reverse=True)
    eligible = eligible[:max(1, int(limit))]
    selected: list[tuple[dict, list[dict]]] = []
    chunk_rows: list[dict] = []
    for offer, missing in eligible:
        if len(chunk_rows) >= budget_remaining:
            break
        allowed = missing[: budget_remaining - len(chunk_rows)]
        if allowed:
            selected.append((offer, allowed))
            chunk_rows.extend({
                **chunk, "user_id": user_id, "job_offer_id": offer["id"]
            } for chunk in allowed)

    if not chunk_rows:
        return {
            **empty, "insufficient": insufficient, "excluded": excluded,
            "eligible_pending": len(eligible),
            "budget_exhausted": bool(eligible) and budget_remaining == 0,
        }

    embedded_so_far = 0

    def persist_batch(start_index: int, batch_texts: list[str], vectors: list[list[float]]) -> None:
        nonlocal embedded_so_far
        rows = []
        for offset, vector in enumerate(vectors):
            source = chunk_rows[start_index + offset]
            rows.append({
                "user_id": user_id, "job_offer_id": source["job_offer_id"],
                "chunk_index": source["chunk_index"], "content": source["content"],
                "embedding_model": settings.embedding_model, "embedding": vector,
            })
        client.table("job_chunks").upsert(
            rows, on_conflict="job_offer_id,chunk_index"
        ).execute()
        # Actualizar memoria local para que el resultado cuente únicamente lo confirmado.
        for row in rows:
            existing_by_offer.setdefault(row["job_offer_id"], set()).add(int(row["chunk_index"]))
        embedded_so_far += len(rows)
        if on_progress:
            on_progress({
                "chunks_saved": embedded_so_far,
                "chunks_total": len(chunk_rows),
                "embedding_batch": start_index // 90 + 1,
            })

    embed_texts(
        [row["content"] for row in chunk_rows],
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        task_type="RETRIEVAL_DOCUMENT",
        on_batch=persist_batch,
    )

    complete = 0
    for offer, _ in selected:
        expected = {int(chunk["chunk_index"]) for chunk in chunk_job_description(
            offer["title"], offer["description"]
        )}
        if expected.issubset(existing_by_offer.get(offer["id"], set())):
            complete += 1

    chunks_saved = len(chunk_rows)
    used_after = used_today + chunks_saved
    eligible_pending = max(0, len(eligible) - complete)
    return {
        "offers_seen": len(offers), "offers_chunked": complete,
        "chunks_saved": chunks_saved, "insufficient": insufficient,
        "excluded": excluded, "eligible_pending": eligible_pending,
        "budget_exhausted": eligible_pending > 0 and used_after >= daily_chunk_limit,
        "budget_remaining": max(0, daily_chunk_limit - used_after),
        "chunks_embedded_last_24h": used_after,
    }


def evaluate_top_offers(
    client: Any, *, user_id: str, top_k: int = 35,
    on_progress: Callable[[dict], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict:
    """Evalúa con Gemini solo el top semántico y ofertas aún no evaluadas con el CV activo."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en .env.")
    daily_evaluation_limit = max(1, int(settings.max_daily_evaluations))
    recent_rows = (client.table("evaluations").select("id").eq("user_id", user_id)
                   .gte("evaluated_at", _rolling_budget_start())
                   .limit(daily_evaluation_limit).execute().data or [])
    daily_remaining = max(0, daily_evaluation_limit - len(recent_rows))
    if daily_remaining == 0:
        pending = client.rpc(
            "rank_job_offers_by_cv", {"match_limit": 1}
        ).execute().data or []
        return {
            "ranked": 0, "evaluated": 0, "below_threshold": 0,
            "minimum_affinity_score": MINIMUM_AFFINITY_SCORE,
            "skipped_existing": 0, "skipped_excluded": 0,
            "errors": [], "results": [], "budget_exhausted": bool(pending),
            "budget_remaining": 0,
        }
    cv_rows = (client.table("cv_versions").select("*").eq("user_id", user_id)
               .eq("is_active", True).limit(1).execute().data or [])
    if not cv_rows:
        raise ValueError("Primero debe procesar su CV.")
    cv_version = cv_rows[0]
    ranked = client.rpc("rank_job_offers_by_cv", {
        "match_limit": max(1, min(int(top_k), daily_remaining, daily_evaluation_limit))
    }).execute().data or []
    ranking_diagnostic = None
    if not ranked:
        chunk_probe = (
            client.table("job_chunks").select("id")
            .eq("user_id", user_id).limit(1).execute().data or []
        )
        ranking_diagnostic = (
            "El ranking semántico devolvió cero candidatos aunque existen fragmentos de ofertas. "
            "Revise el contexto de autenticación del RPC rank_job_offers_by_cv."
            if chunk_probe else
            "No hay fragmentos semánticos de ofertas disponibles para evaluar. "
            "La preparación está pendiente o alcanzó su presupuesto diario."
        )
    stats = {"ranked": len(ranked), "evaluated": 0, "below_threshold": 0,
             "minimum_affinity_score": MINIMUM_AFFINITY_SCORE,
             "skipped_existing": 0, "skipped_excluded": 0,
             "errors": [ranking_diagnostic] if ranking_diagnostic else [],
             "results": [], "review_results": [], "budget_exhausted": False,
             "budget_remaining": daily_remaining, "api_quota_paused": False,
             "api_quota_message": None, "retry_after_seconds": None}
    def notify_evaluation(processed: int) -> None:
        if on_progress:
            on_progress({
                "offers_processed": processed,
                "offers_total": len(ranked),
                "evaluated": stats["evaluated"],
                "errors": len(stats["errors"]),
            })

    for candidate_index, candidate in enumerate(ranked, start=1):
        if should_cancel and should_cancel():
            stats["cancelled"] = True
            break
        offer_id = candidate["job_offer_id"]
        previous = (client.table("evaluations").select("id")
                    .eq("user_id", user_id).eq("job_offer_id", offer_id)
                    .eq("cv_version_id", cv_version["id"]).limit(1).execute().data or [])
        if previous:
            stats["skipped_existing"] += 1
            notify_evaluation(candidate_index)
            continue
        offer_rows = (client.table("job_offers").select("*").eq("id", offer_id)
                      .eq("user_id", user_id).limit(1).execute().data or [])
        if not offer_rows:
            notify_evaluation(candidate_index)
            continue
        offer = offer_rows[0]
        reason = _excluded_reason(offer)
        sector = classify_sector(offer)
        if reason:
            metadata = offer.get("raw_metadata") or {}
            client.table("job_offers").update({
                "sector_category": sector,
                "raw_metadata": {**metadata, "evaluation_filter": reason}
            }).eq("id", offer_id).eq("user_id", user_id).execute()
            stats["skipped_excluded"] += 1
            notify_evaluation(candidate_index)
            continue
        evidence_rows = (client.rpc("retrieve_cv_evidence_for_offer", {
            "target_job_offer_id": offer_id, "match_count": CV_EVIDENCE_MATCH_COUNT
        }).execute().data or [])
        evidence = [{
            "chunk_id": row["chunk_id"], "section": row["section"],
            "text": row["content"], "similarity": row["similarity"]
        } for row in evidence_rows]
        if not evidence:
            stats["errors"].append(f"{offer.get('title')}: no se recuperó evidencia CV.")
            notify_evaluation(candidate_index)
            continue
        try:
            description = (offer.get("description") or "").strip()
            if len(description) > MAX_EVALUATION_DESCRIPTION_CHARS:
                description = (
                    description[:8000]
                    + "\n\n[Se omitió una sección intermedia extensa para controlar el consumo de tokens.]\n\n"
                    + description[-2000:]
                )
            evaluation_offer = {
                key: offer.get(key)
                for key in (
                    "title", "company", "location", "employment_type",
                    "salary_text", "source", "source_url", "published_at", "job_hash",
                )
                if offer.get(key) is not None
            }
            evaluation_offer["description"] = description
            run = evaluate_offer(
                evaluation_offer,
                {"cv_hash": cv_version["cv_hash"],
                 "filename": cv_version.get("source_filename"),
                 "page_count": cv_version.get("page_count"),
                 "char_count": cv_version.get("char_count"),
                 "target_strategy": TARGET_STRATEGY},
                evidence,
            )
            saved = save_evaluation(
                client, user_id=user_id, offer_id=offer_id,
                cv_version_id=cv_version["id"], run=run,
            )
            evaluation = run["evaluation"]
            affinity = int(evaluation["score_match"])
            priority = _priority_score(affinity, sector)
            metadata = offer.get("raw_metadata") or {}
            metadata["semantic_preselection"] = {
                "similarity": candidate.get("semantic_score"),
                "matching_job_chunks": candidate.get("matching_job_chunk_count"),
                "method": "rank_job_offers_by_cv"
            }
            salary_analysis = analyse_salary(offer.get("salary_text"))
            opportunity_score = attractiveness_score(affinity, salary_analysis)
            evaluation["salary_assessment"] = salary_analysis["label"]
            metadata["evaluation"] = {
                "evaluation_id": saved["id"], "model": run["model"],
                "prompt_version": run["prompt_version"], "cv_version_id": cv_version["id"],
                "strengths": evaluation.get("strengths", []),
                "gaps": evaluation.get("gaps", []),
                "role_detected": evaluation.get("role_detected"),
                "salary_preference": salary_analysis,
                "attractiveness_score": opportunity_score,
            }
            client.table("job_offers").update({
                "affinity_score": affinity, "priority_score": priority,
                "sector_category": sector, "raw_metadata": metadata,
            }).eq("id", offer_id).eq("user_id", user_id).execute()
            stats["evaluated"] += 1
            notify_evaluation(candidate_index)
            if not meets_affinity_threshold(affinity):
                # Se conserva para la bandeja de revisión; el umbral no elimina oportunidades.
                stats["below_threshold"] += 1
                if affinity >= MANUAL_REVIEW_MINIMUM_SCORE:
                    stats.setdefault("review_results", []).append({
                        "id": offer_id, "title": offer["title"], "company": offer.get("company"),
                        "source_url": offer.get("source_url"), "affinity_score": affinity,
                        "priority_score": priority, "attractiveness_score": opportunity_score,
                        "salary_preference": salary_analysis,
                        "sector_category": sector, "verdict": evaluation["verdict"],
                    })
                continue
            stats["results"].append({
                "id": offer_id, "title": offer["title"], "company": offer.get("company"),
                "source_url": offer.get("source_url"), "affinity_score": affinity,
                "priority_score": priority, "attractiveness_score": opportunity_score,
                "salary_preference": salary_analysis,
                "sector_category": sector, "verdict": evaluation["verdict"],
                "semantic_similarity": candidate.get("semantic_score"),
            })
        except GeminiEvaluationDeferred as exc:
            stats["api_quota_paused"] = True
            stats["api_quota_message"] = str(exc)
            stats["retry_after_seconds"] = exc.retry_after_seconds
            logger.warning("Evaluación pausada por cuota Gemini: %s", exc)
            notify_evaluation(candidate_index)
            break
        except Exception as exc:
            logger.exception("Falló evaluación de oferta %s", offer_id)
            stats["errors"].append(f"{offer.get('title')}: {type(exc).__name__}: {exc}")
            notify_evaluation(candidate_index)
    # La compatibilidad profesional manda; el sector solo desempata.
    stats["results"].sort(
        key=lambda item: (item.get("attractiveness_score", item["affinity_score"]), item["affinity_score"], item["priority_score"]),
        reverse=True,
    )
    stats["review_results"].sort(
        key=lambda item: (item.get("attractiveness_score", item["affinity_score"]), item["affinity_score"]),
        reverse=True,
    )
    stats["budget_remaining"] = max(0, daily_remaining - stats["evaluated"])
    if stats["budget_remaining"] == 0:
        # Consulta pgvector/SQL sin Gemini para distinguir cuota agotada de trabajo terminado.
        pending = client.rpc(
            "rank_job_offers_by_cv", {"match_limit": 1}
        ).execute().data or []
        stats["budget_exhausted"] = bool(pending)
    return stats



def get_processing_status(client: Any, *, user_id: str) -> dict:
    """Calcula pendientes reales por chunk y el presupuesto de embeddings disponible."""
    offers = (client.table("job_offers").select("id,title,company,description,raw_metadata")
              .eq("user_id", user_id).eq("lifecycle_status", "NUEVA")
              .limit(2000).execute().data or [])
    offer_ids = [row["id"] for row in offers]
    chunk_rows = []
    for start in range(0, len(offer_ids), 100):
        chunk_rows.extend(
            client.table("job_chunks").select("job_offer_id,chunk_index")
            .eq("user_id", user_id).in_("job_offer_id", offer_ids[start:start + 100])
            .execute().data or []
        )
    present: dict[str, set[int]] = {}
    for row in chunk_rows:
        present.setdefault(row["job_offer_id"], set()).add(int(row["chunk_index"]))

    eligible = [row for row in offers
                if not (row.get("raw_metadata") or {}).get("evaluation_filter")
                and not _excluded_reason(row)]
    pending = 0
    complete = 0
    needs_description = 0
    for row in eligible:
        description = (row.get("description") or "").strip()
        if len(description) < 150:
            needs_description += 1
            continue
        expected = {int(chunk["chunk_index"]) for chunk in chunk_job_description(
            row["title"], description
        )}
        if expected.issubset(present.get(row["id"], set())):
            complete += 1
        else:
            pending += 1

    chunks_used = _daily_chunk_usage(client, user_id=user_id)
    return {
        "new_offers": len(offers),
        "chunked_offers": complete,
        "pending_chunking": pending,
        "needs_description": needs_description,
        "excluded_by_preferences": len(offers) - len(eligible),
        "chunks_embedded_last_24h": chunks_used,
        "daily_chunk_budget_remaining": max(0, int(get_settings().max_daily_job_chunks) - chunks_used),
    }
