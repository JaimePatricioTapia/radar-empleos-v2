"""Pipeline económico: Job Chunks -> embeddings -> ranking vectorial -> Gemini."""
from __future__ import annotations

import logging
from typing import Any

from src.config import get_settings
from src.cv.embeddings import embed_texts
from src.db.repository import save_evaluation
from src.evaluation.evaluator import evaluate_offer
from src.search.job_chunker import chunk_job_description

logger = logging.getLogger(__name__)

SECTOR_WEIGHTS = {
    "MINERIA": 100,
    "PROVEEDOR_MINERO": 92,
    "TECNOLOGIA_CONSULTORIA": 62,
    "BANCA_FINANZAS": 52,
    "OTROS": 30,
}
EXCLUDED_ROLE_TERMS = ("scrum master",)
EXCLUDED_COMPANIES = ("banco santander", "santander chile")
HEALTH_TERMS = ("isapre", "clínica", "clinica", "hospital", "centro médico", "centro medico")


def classify_sector(offer: dict) -> str:
    title = (offer.get("title") or "").lower()
    company = (offer.get("company") or "").lower()
    text = f"{title} {company} {(offer.get('description') or '')[:5000]}".lower()
    mining_terms = ("minería", "mineria", "minera", "minero", "codelco", "bhp",
                    "escondida", "collahuasi", "sqm", "teck", "antofagasta minerals",
                    "chuquicamata", "el teniente", "faena", "rajo", "subterránea",
                    "subterranea", "raise boring")
    supplier_terms = ("proveedor", "contratista", "servicios mineros", "equipos mineros",
                      "perforación", "perforacion", "maquinaria", "finning",
                      "master drilling", "komatsu", "echeverría izquierdo")
    bank_terms = ("banco", "banca", "financiero", "financiera", "fintech", "seguros",
                  "medios de pago", "inversiones")
    tech_terms = ("consultoría", "consultoria", "tecnología", "tecnologia", "software",
                  "transformación digital", "transformacion digital", "sistemas")
    if any(term in company or term in title for term in mining_terms):
        return "MINERIA"
    if any(term in text for term in mining_terms) and any(term in text for term in supplier_terms):
        return "PROVEEDOR_MINERO"
    if any(term in company or term in title for term in bank_terms):
        return "BANCA_FINANZAS"
    if any(term in text for term in tech_terms):
        return "TECNOLOGIA_CONSULTORIA"
    return "OTROS"


def _excluded_reason(offer: dict) -> str | None:
    title = (offer.get("title") or "").lower()
    company = (offer.get("company") or "").lower()
    if any(term in title for term in EXCLUDED_ROLE_TERMS):
        return "Cargo Scrum Master fuera de los objetivos actuales."
    if any(term in company for term in EXCLUDED_COMPANIES):
        return "Empresa excluida de las preferencias actuales."
    if any(term in f"{title} {company}" for term in HEALTH_TERMS):
        return "Sector salud fuera de las preferencias actuales."
    return None


def _priority_score(affinity: int, sector: str) -> int:
    """Prioridad estratégica separada de la afinidad: 75% afinidad + 25% sector."""
    sector_weight = SECTOR_WEIGHTS.get(sector, 30)
    return max(0, min(100, int(0.75 * affinity + 0.25 * sector_weight + 0.5)))


def build_job_chunks(client: Any, *, user_id: str, limit: int = 100) -> dict:
    """Genera chunks/embeddings solo para ofertas nuevas que aún no se procesaron."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en .env.")
    offers = (client.table("job_offers")
              .select("id,title,company,description,raw_metadata,lifecycle_status")
              .eq("user_id", user_id).eq("lifecycle_status", "NUEVA")
              .order("captured_at", desc=True).limit(1000).execute().data or [])
    if not offers:
        return {"offers_seen": 0, "offers_chunked": 0, "chunks_saved": 0, "insufficient": 0}

    offer_ids = [item["id"] for item in offers]
    existing_rows = []
    for start in range(0, len(offer_ids), 100):
        existing_rows.extend(
            client.table("job_chunks").select("job_offer_id")
            .eq("user_id", user_id).in_("job_offer_id", offer_ids[start:start + 100])
            .execute().data or []
        )
    already = {row["job_offer_id"] for row in existing_rows}
    pending, chunk_rows = [], []
    insufficient = 0
    excluded = 0
    for offer in offers:
        if offer["id"] in already:
            continue
        metadata = offer.get("raw_metadata") or {}
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
            client.table("job_offers").update({
                "raw_metadata": {**metadata, "processing": {
                    "status": "needs_description", "reason": "Descripción insuficiente para evaluación fiable."
                }}
            }).eq("id", offer["id"]).eq("user_id", user_id).execute()
            continue
        chunks = chunk_job_description(offer["title"], description)
        if not chunks:
            insufficient += 1
            continue
        pending.append(offer)
        for chunk in chunks:
            chunk_rows.append({**chunk, "user_id": user_id, "job_offer_id": offer["id"]})
        for chunk in chunks:
            chunk_rows.append({**chunk, "user_id": user_id, "job_offer_id": offer["id"]})

    if not chunk_rows:
        return {"offers_seen": len(offers), "offers_chunked": 0, "chunks_saved": 0,
                "insufficient": insufficient}
    vectors = embed_texts(
        [row["content"] for row in chunk_rows], api_key=settings.gemini_api_key,
        model=settings.embedding_model, task_type="RETRIEVAL_DOCUMENT",
    )
    rows = []
    for row, vector in zip(chunk_rows, vectors):
        rows.append({
            "user_id": row["user_id"], "job_offer_id": row["job_offer_id"],
            "chunk_index": row["chunk_index"], "content": row["content"],
            "embedding_model": settings.embedding_model, "embedding": vector,
        })
    for start in range(0, len(rows), 100):
        client.table("job_chunks").upsert(
            rows[start:start + 100], on_conflict="job_offer_id,chunk_index"
        ).execute()
    return {"offers_seen": len(offers), "offers_chunked": len(pending),
            "chunks_saved": len(rows), "insufficient": insufficient}


def evaluate_top_offers(client: Any, *, user_id: str, top_k: int = 35) -> dict:
    """Evalúa con Gemini solo el top semántico y ofertas aún no evaluadas con el CV activo."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en .env.")
    cv_rows = (client.table("cv_versions").select("*").eq("user_id", user_id)
               .eq("is_active", True).limit(1).execute().data or [])
    if not cv_rows:
        raise ValueError("Primero debe procesar su CV.")
    cv_version = cv_rows[0]
    ranked = client.rpc("rank_job_offers_by_cv", {"match_limit": max(1, min(top_k, 100))}).execute().data or []
    stats = {"ranked": len(ranked), "evaluated": 0, "skipped_existing": 0,
             "skipped_excluded": 0, "errors": [], "results": []}
    for candidate in ranked:
        offer_id = candidate["job_offer_id"]
        previous = (client.table("evaluations").select("id")
                    .eq("user_id", user_id).eq("job_offer_id", offer_id)
                    .eq("cv_version_id", cv_version["id"]).limit(1).execute().data or [])
        if previous:
            stats["skipped_existing"] += 1
            continue
        offer_rows = (client.table("job_offers").select("*").eq("id", offer_id)
                      .eq("user_id", user_id).limit(1).execute().data or [])
        if not offer_rows:
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
            continue
        evidence_rows = (client.rpc("retrieve_cv_evidence_for_offer", {
            "target_job_offer_id": offer_id, "match_count": 10
        }).execute().data or [])
        evidence = [{
            "chunk_id": row["chunk_id"], "section": row["section"],
            "text": row["content"], "similarity": row["similarity"]
        } for row in evidence_rows]
        if not evidence:
            stats["errors"].append(f"{offer.get('title')}: no se recuperó evidencia CV.")
            continue
        try:
            run = evaluate_offer(
                offer,
                {"cv_hash": cv_version["cv_hash"],
                 "filename": cv_version.get("source_filename"),
                 "page_count": cv_version.get("page_count"),
                 "char_count": cv_version.get("char_count")},
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
            metadata["evaluation"] = {
                "evaluation_id": saved["id"], "model": run["model"],
                "prompt_version": run["prompt_version"], "cv_version_id": cv_version["id"],
                "strengths": evaluation.get("strengths", []),
                "gaps": evaluation.get("gaps", []),
                "role_detected": evaluation.get("role_detected"),
            }
            client.table("job_offers").update({
                "affinity_score": affinity, "priority_score": priority,
                "sector_category": sector, "raw_metadata": metadata,
            }).eq("id", offer_id).eq("user_id", user_id).execute()
            stats["evaluated"] += 1
            stats["results"].append({
                "id": offer_id, "title": offer["title"], "company": offer.get("company"),
                "source_url": offer.get("source_url"), "affinity_score": affinity,
                "priority_score": priority, "sector_category": sector,
                "verdict": evaluation["verdict"],
                "semantic_similarity": candidate.get("semantic_score"),
            })
        except Exception as exc:
            logger.exception("Falló evaluación de oferta %s", offer_id)
            stats["errors"].append(f"{offer.get('title')}: {type(exc).__name__}: {exc}")
    stats["results"].sort(key=lambda item: (item["priority_score"], item["affinity_score"]), reverse=True)
    return stats



def get_processing_status(client: Any, *, user_id: str) -> dict:
    """Cuenta ofertas NUEVA aptas, procesadas y pendientes de fragmentación."""
    offers = (client.table("job_offers").select("id,description")
              .eq("user_id", user_id).eq("lifecycle_status", "NUEVA")
              .limit(2000).execute().data or [])
    offer_ids = {row["id"] for row in offers}
    chunk_rows = (client.table("job_chunks").select("job_offer_id")
                  .eq("user_id", user_id).limit(20000).execute().data or [])
    chunked_ids = {row["job_offer_id"] for row in chunk_rows if row["job_offer_id"] in offer_ids}
    eligible_ids = {row["id"] for row in offers if len((row.get("description") or "").strip()) >= 150}
    return {
        "new_offers": len(offers),
        "chunked_offers": len(chunked_ids),
        "pending_chunking": len(eligible_ids - chunked_ids),
        "needs_description": len(offers) - len(eligible_ids),
    }
