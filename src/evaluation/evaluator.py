"""Evaluador Gemini con salida validada y trazabilidad de ejecución."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from google import genai
from src.config import get_settings
from src.evaluation.schemas import OfferEvaluation

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "evaluator_system.md"


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def evaluate_offer(
    offer: dict,
    cv_profile: dict,
    evidence_chunks: list[dict],
    *,
    client=None,
    model: str | None = None,
) -> dict:
    """Evalúa una oferta contra perfil y evidencia recuperada.

    La recuperación semántica se ejecuta fuera de esta función para poder
    probar el evaluador con evidencia controlada y reproducible.
    """
    settings = get_settings()
    if client is None:
        if not settings.gemini_api_key:
            raise ValueError("Falta GEMINI_API_KEY.")
        client = genai.Client(api_key=settings.gemini_api_key)

    model_name = model or settings.gemini_model
    prompt_version = hashlib.sha256(load_system_prompt().encode()).hexdigest()[:12]
    payload = {
        "offer": offer,
        "cv_profile": cv_profile,
        "retrieved_cv_evidence": [
            {"section": item.get("section"), "chunk_id": item.get("chunk_id"), "text": item.get("text")}
            for item in evidence_chunks
        ],
    }
    response = client.models.generate_content(
        model=model_name,
        contents=(load_system_prompt() + "\\n\\nINPUT JSON:\\n" + json.dumps(payload, ensure_ascii=False)),
        config={
            "response_mime_type": "application/json",
            "response_schema": OfferEvaluation,
            "temperature": 0,
        },
    )
    result = OfferEvaluation.model_validate_json(response.text).model_dump()
    return {
        "evaluation": result,
        "model": model_name,
        "prompt_version": prompt_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "cv_hash": cv_profile.get("cv_hash"),
        "offer_hash": offer.get("job_hash"),
        "evidence_chunk_ids": [item.get("chunk_id") for item in evidence_chunks],
    }
