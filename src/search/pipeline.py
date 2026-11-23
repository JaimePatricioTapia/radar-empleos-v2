"""Orquestador de una sola acción para búsqueda, preparación y evaluación."""
from __future__ import annotations

from typing import Callable, Any

from src.config import get_settings
from src.search.ingestion import run_discovery
from src.search.processing import (
    build_job_chunks,
    evaluate_top_offers,
    get_processing_status,
)


def run_full_search_pipeline(
    client: Any,
    *,
    user_id: str,
    roles: list[str],
    sources: list[str],
    limit_per_query: int = 10,
    progress: Callable[[str], None] | None = None,
    chunk_batch_size: int = 100,
    evaluation_batch_size: int = 1000,
) -> dict:
    """Ejecuta las etapas completas; conserva en DB cada resultado confirmado.

    Los lotes se repiten hasta completar el trabajo o alcanzar el presupuesto
    gratuito móvil de 24 horas. Cada sublote confirmado queda guardado y puede
    reanudarse sin recalcular fragmentos ya persistidos.
    """
    active_cv = (
        client.table("cv_versions")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not active_cv:
        raise ValueError("Primero debe procesar su currículum.")

    def report(message: str) -> None:
        if progress:
            progress(message)

    report("Etapa 1/3 · Buscando ofertas en los portales seleccionados…")
    discovery = run_discovery(
        client,
        user_id=user_id,
        roles=roles,
        sources=sources,
        limit_per_query=limit_per_query,
        progress=progress,
    )

    preparation = {
        "offers_chunked": 0,
        "chunks_saved": 0,
        "insufficient": 0,
        "excluded": 0,
        "batches": 0,
        "pending_remaining": 0,
        "budget_exhausted": False,
        "budget_remaining": 0,
        "chunks_embedded_last_24h": 0,
    }
    report("Etapa 2/3 · Preparando descripciones y embeddings…")
    previous_pending = None
    default_chunk_budget = max(1, int(get_settings().max_daily_job_chunks))
    while True:
        status = get_processing_status(client, user_id=user_id)
        pending = int(status["pending_chunking"])
        preparation["budget_remaining"] = int(
            status.get("daily_chunk_budget_remaining", default_chunk_budget)
        )
        preparation["chunks_embedded_last_24h"] = int(status.get("chunks_embedded_last_24h", 0))
        if pending == 0:
            break
        if preparation["budget_remaining"] <= 0:
            preparation["budget_exhausted"] = True
            preparation["pending_remaining"] = pending
            break
        if previous_pending is not None and pending >= previous_pending:
            preparation["pending_remaining"] = pending
            raise RuntimeError(
                "La preparación no redujo las ofertas pendientes. "
                "Se conservaron los resultados guardados; puede reintentar."
            )
        previous_pending = pending
        batch = build_job_chunks(
            client,
            user_id=user_id,
            limit=max(1, min(int(chunk_batch_size), pending)),
        )
        preparation["offers_chunked"] += int(batch.get("offers_chunked", 0))
        preparation["chunks_saved"] += int(batch.get("chunks_saved", 0))
        preparation["insufficient"] += int(batch.get("insufficient", 0))
        preparation["excluded"] += int(batch.get("excluded", 0))
        preparation["batches"] += 1
        preparation["budget_remaining"] = int(batch.get("budget_remaining", 0))
        preparation["chunks_embedded_last_24h"] = int(batch.get("chunks_embedded_last_24h", 0))
        report(
            f"Preparación: {preparation['offers_chunked']} ofertas completadas; "
            f"{preparation['chunks_saved']} fragmentos guardados; "
            f"presupuesto gratuito restante: {preparation['budget_remaining']} fragmentos."
        )
        if batch.get("budget_exhausted"):
            preparation["budget_exhausted"] = True
            break
        next_status = get_processing_status(client, user_id=user_id)
        next_pending = int(next_status["pending_chunking"])
        if next_pending >= pending:
            preparation["pending_remaining"] = next_pending
            raise RuntimeError(
                "La preparación se detuvo sin avanzar. Los fragmentos guardados "
                "se conservan y el siguiente intento continuará solo con los faltantes."
            )
    final_status = get_processing_status(client, user_id=user_id)
    preparation["pending_remaining"] = int(final_status["pending_chunking"])
    preparation["status"] = final_status

    evaluation = {
        "ranked": 0,
        "evaluated": 0,
        "below_threshold": 0,
        "skipped_existing": 0,
        "skipped_excluded": 0,
        "errors": [],
        "results": [],
        "batches": 0,
        "budget_exhausted": False,
        "budget_remaining": 15,
    }
    report("Etapa 3/3 · Comparando requisitos de las ofertas con evidencia del CV…")
    configured_daily_limit = max(1, int(get_settings().max_daily_evaluations))
    evaluation_limit = max(1, min(int(evaluation_batch_size), configured_daily_limit))
    while True:
        batch = evaluate_top_offers(
            client,
            user_id=user_id,
            top_k=evaluation_limit,
        )
        evaluation["ranked"] += int(batch.get("ranked", 0))
        evaluation["evaluated"] += int(batch.get("evaluated", 0))
        evaluation["below_threshold"] += int(batch.get("below_threshold", 0))
        evaluation["skipped_existing"] += int(batch.get("skipped_existing", 0))
        evaluation["skipped_excluded"] += int(batch.get("skipped_excluded", 0))
        evaluation["errors"].extend(batch.get("errors", []))
        evaluation["results"].extend(batch.get("results", []))
        evaluation["batches"] += 1
        evaluation["budget_remaining"] = int(batch.get("budget_remaining", 0))
        evaluation["budget_exhausted"] = bool(batch.get("budget_exhausted", False))
        report(
            f"Evaluación: {evaluation['evaluated']} ofertas evaluadas; "
            f"{len(evaluation['errors'])} incidencias."
        )
        if batch.get("errors") or batch.get("budget_exhausted") or int(batch.get("ranked", 0)) < evaluation_limit:
            break
        if int(batch.get("evaluated", 0)) == 0:
            break

    evaluation["results"].sort(
        key=lambda item: (item["affinity_score"], item["priority_score"]),
        reverse=True,
    )
    return {
        "discovery": discovery,
        "preparation": preparation,
        "evaluation": evaluation,
        "processing_status": final_status,
        "paused_for_free_quota": bool(
            preparation["budget_exhausted"] or evaluation["budget_exhausted"]
        ),
        "completed": (
            not evaluation["errors"]
            and preparation["pending_remaining"] == 0
            and int(discovery.get("errors", 0)) == 0
            and not preparation["budget_exhausted"]
            and not evaluation["budget_exhausted"]
        ),
    }
