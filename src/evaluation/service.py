"""Caso de uso: oferta -> evidencia CV -> evaluación Gemini -> historial."""
from __future__ import annotations

import hashlib

from src.search.salary import analyse_salary
from src.cv.skills_profile import derive_skills_profile

from src.config import get_settings
from src.db.repository import upsert_job_offer, save_evaluation
from src.evaluation.evaluator import evaluate_offer
from src.search.retriever import retrieve_cv_evidence
from src.search.processing import (
    TARGET_STRATEGY,
    _rolling_budget_start,
)


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

    # Reutilizar una evaluación ya hecha con el mismo aviso y versión del CV.
    previous = (
        client.table("evaluations")
        .select("id,result_json,model,prompt_version,evidence_chunk_ids")
        .eq("user_id", user_id)
        .eq("job_offer_id", saved_offer["id"])
        .eq("cv_version_id", cv_version["id"])
        .limit(1).execute().data or []
    )
    if previous:
        cached = previous[0]
        evidence_ids = cached.get("evidence_chunk_ids") or []
        evidence_rows = []
        if evidence_ids:
            evidence_rows = (
                client.table("cv_chunks")
                .select("chunk_id,section,content")
                .eq("user_id", user_id).eq("cv_version_id", cv_version["id"])
                .in_("chunk_id", evidence_ids).execute().data or []
            )
        return {
            "offer": saved_offer,
            "evaluation": cached["result_json"],
            "evaluation_id": cached["id"],
            "evidence": [
                {"chunk_id": row["chunk_id"], "section": row["section"],
                 "text": row["content"], "similarity": None}
                for row in evidence_rows
            ],
            "model": cached["model"],
            "prompt_version": cached["prompt_version"],
            "cached": True,
        }

    daily_limit = max(1, int(settings.max_daily_evaluations))
    recent = (
        client.table("evaluations").select("id").eq("user_id", user_id)
        .gte("evaluated_at", _rolling_budget_start())
        .limit(daily_limit).execute().data or []
    )
    if len(recent) >= daily_limit:
        raise RuntimeError(
            "Se alcanzó el límite preventivo gratuito de evaluaciones configurado en las "
            "últimas 24 horas. No se llamó a Gemini; inténtelo cuando se renueve la ventana."
        )

    compact_description = description
    if len(compact_description) > 10000:
        compact_description = (
            compact_description[:8000]
            + "\n\n[Se omitió una sección intermedia extensa para controlar el consumo de tokens.]\n\n"
            + compact_description[-2000:]
        )
    query = f"Cargo: {title}\nEmpresa: {offer.get('company') or 'No informada'}\nDescripción: {compact_description}"
    evidence = retrieve_cv_evidence(
        query,
        client=client,
        api_key=settings.gemini_api_key,
        model=settings.embedding_model,
        cv_version_id=cv_version["id"],
    )
    if not evidence:
        raise ValueError("No se encontró evidencia del CV activo. Procese nuevamente el CV.")

    evaluation_offer = {
        "title": title,
        "company": offer.get("company"),
        "location": offer.get("location"),
        "source_url": offer.get("source_url"),
        "source": offer.get("source") or "manual",
        "job_hash": normalized["job_hash"],
        "description": compact_description,
    }
    cv_chunk_rows = (client.table("cv_chunks").select("chunk_id,section,content")
                     .eq("user_id", user_id).eq("cv_version_id", cv_version["id"])
                     .limit(500).execute().data or [])
    skills_profile = derive_skills_profile(cv_chunk_rows)
    run = evaluate_offer(
        evaluation_offer,
        {
            "cv_hash": cv_version["cv_hash"],
            "filename": cv_version.get("source_filename"),
            "page_count": cv_version.get("page_count"),
            "char_count": cv_version.get("char_count"),
            "target_strategy": TARGET_STRATEGY,
            "skills_profile": skills_profile,
        },
        evidence,
    )
    salary_analysis = analyse_salary(offer.get("salary_text"))
    run["evaluation"]["salary_assessment"] = salary_analysis["label"]
    run["evaluation"]["salary_preference"] = salary_analysis
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
        "cached": False,
    }
