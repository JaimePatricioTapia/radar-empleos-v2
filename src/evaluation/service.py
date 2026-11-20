"""Caso de uso: oferta -> evidencia CV -> evaluación Gemini -> historial."""
from __future__ import annotations

import hashlib

from src.config import get_settings
from src.db.repository import upsert_job_offer, save_evaluation
from src.evaluation.evaluator import evaluate_offer
from src.search.retriever import retrieve_cv_evidence
from src.search.processing import TARGET_STRATEGY


def evaluate_job_offer(offer: dict, *, client, user_id: str) -> dict:
    title = (offer.get("title") or "").strip()
    description = (offer.get("description") or "").strip()
    if not title or not description:
        raise ValueError("La oferta debe incluir cargo y descripción.")
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("Falta GEMINI_API_KEY en .env.")

    normalized = {
        **offer,
        "title": title,
        "description": description,
        "job_hash": hashlib.sha256(f"{title}\n{description}".encode("utf-8")).hexdigest(),
    }
    cv_result = (
        client.table("cv_versions")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not cv_result.data:
        raise ValueError("Primero debe procesar su CV.")
    cv_version = cv_result.data[0]

    saved_offer = upsert_job_offer(client, user_id=user_id, offer=normalized)
    query = f"Cargo: {title}\nEmpresa: {offer.get('company') or 'No informada'}\nDescripción: {description}"
    evidence = retrieve_cv_evidence(
        query,
        client=client,
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        cv_version_id=cv_version["id"],
    )
    if not evidence:
        raise ValueError("No se encontró evidencia del CV activo. Procese nuevamente el CV.")

    run = evaluate_offer(
        normalized,
        {
            "cv_hash": cv_version["cv_hash"],
            "filename": cv_version.get("source_filename"),
            "page_count": cv_version.get("page_count"),
            "char_count": cv_version.get("char_count"),
            "target_strategy": TARGET_STRATEGY,
        },
        evidence,
    )
    saved = save_evaluation(
        client,
        user_id=user_id,
        offer_id=saved_offer["id"],
        cv_version_id=cv_version["id"],
        run=run,
    )
    return {
        "offer": saved_offer,
        "evaluation": run["evaluation"],
        "evaluation_id": saved["id"],
        "evidence": evidence,
        "model": run["model"],
        "prompt_version": run["prompt_version"],
    }
