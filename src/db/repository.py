"""Operaciones de persistencia de Radar 2.0.

El cliente debe representar una sesión autenticada de Supabase. Las políticas
RLS verifican que user_id coincida con auth.uid(); no se usa service_role.
"""
from __future__ import annotations

from typing import Any


def save_cv_snapshot(
    client: Any,
    *,
    user_id: str,
    cv_metadata: dict,
    chunks: list[dict],
    embeddings: list[list[float]],
    embedding_model: str,
    chunker_version: str,
) -> dict:
    if len(chunks) != len(embeddings):
        raise ValueError("Debe existir exactamente un embedding por chunk.")
    if not chunks:
        raise ValueError("No se puede guardar una versión del CV sin chunks.")
    if any(len(vector) != 3072 for vector in embeddings):
        raise ValueError("Cada embedding debe tener 3.072 dimensiones.")

    cv_hash = cv_metadata["cv_hash"]
    version_payload = {
        "user_id": user_id,
        "cv_hash": cv_hash,
        "source_filename": cv_metadata.get("filename"),
        "page_count": cv_metadata.get("page_count"),
        "char_count": cv_metadata.get("char_count", cv_metadata.get("character_count")),
        "chunker_version": chunker_version,
        "embedding_model": embedding_model,
        "embedding_dimensions": 3072,
        "is_active": False,
    }
    version_result = (
        client.table("cv_versions")
        .upsert(version_payload, on_conflict="user_id,cv_hash")
        .execute()
    )
    version = version_result.data[0]
    version_id = version["id"]

    rows = []
    for index, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "user_id": user_id,
            "cv_version_id": version_id,
            "chunk_id": chunk["chunk_id"],
            "chunk_index": index,
            "section": chunk.get("section", "general"),
            "content": chunk["text"],
            "char_count": chunk.get("char_count", len(chunk["text"])),
            "embedding_model": embedding_model,
            "embedding": vector,
        })
    # Primero insertar/actualizar todo lo nuevo. No borrar la versión anterior
    # hasta que la carga haya terminado correctamente.
    client.table("cv_chunks").upsert(
        rows, on_conflict="cv_version_id,chunk_id"
    ).execute()
    current_ids = [row["chunk_id"] for row in rows]
    client.table("cv_chunks").delete().eq(
        "cv_version_id", version_id
    ).not_.in_("chunk_id", current_ids).execute()

    # Activar al final: la versión anterior permanece activa si la carga falla.
    client.table("cv_versions").update({"is_active": False}).eq("user_id", user_id).neq("id", version_id).execute()
    client.table("cv_versions").update({"is_active": True}).eq("id", version_id).eq("user_id", user_id).execute()
    return {"cv_version_id": version_id, "cv_hash": cv_hash, "chunk_count": len(rows)}


def upsert_job_offer(client: Any, *, user_id: str, offer: dict) -> dict:
    required = ("title", "description", "job_hash")
    missing = [field for field in required if not offer.get(field)]
    if missing:
        raise ValueError(f"Faltan campos obligatorios de la oferta: {', '.join(missing)}")
    payload = {
        "user_id": user_id,
        "source": offer.get("source"),
        "source_url": offer.get("source_url"),
        "external_id": offer.get("external_id"),
        "title": offer["title"],
        "company": offer.get("company"),
        "location": offer.get("location"),
        "employment_type": offer.get("employment_type"),
        "salary_text": offer.get("salary_text"),
        "description": offer["description"],
        "job_hash": offer["job_hash"],
        "published_at": offer.get("published_at"),
        "raw_metadata": offer.get("raw_metadata", {}),
    }
    result = client.table("job_offers").upsert(payload, on_conflict="user_id,job_hash").execute()
    return result.data[0]


def save_evaluation(client: Any, *, user_id: str, offer_id: str, cv_version_id: str, run: dict) -> dict:
    evaluation = run["evaluation"]
    payload = {
        "user_id": user_id,
        "job_offer_id": offer_id,
        "cv_version_id": cv_version_id,
        "score_match": evaluation["score_match"],
        "verdict": evaluation["verdict"],
        "model": run["model"],
        "prompt_version": run["prompt_version"],
        "result_json": evaluation,
        "evidence_chunk_ids": run.get("evidence_chunk_ids", []),
        "evaluated_at": run.get("evaluated_at"),
    }
    result = client.table("evaluations").insert(payload).execute()
    return result.data[0]
