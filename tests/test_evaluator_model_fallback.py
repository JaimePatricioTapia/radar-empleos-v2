import json
from types import SimpleNamespace

from src.evaluation.evaluator import FALLBACK_MODEL, evaluate_offer


def test_evaluator_falls_back_when_configured_gemini_model_is_retired(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            if len(calls) == 1:
                raise RuntimeError(
                    "404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users"
                )
            return SimpleNamespace(text=json.dumps({
                "score_match": 88,
                "verdict": "POSTULAR",
                "role_detected": "Business Analyst",
                "strengths": ["Experiencia en análisis funcional"],
                "gaps": [],
                "hard_constraints": [],
                "evidence": [],
                "uncertainty_notes": [],
                "salary_assessment": "No informado",
                "cv_focus_recommendation": "Destacar experiencia relevante",
                "ats_keywords": ["Business Analyst"],
            }))

    monkeypatch.setattr(
        "src.evaluation.evaluator.get_settings",
        lambda: SimpleNamespace(gemini_api_key="fake", gemini_model="gemini-2.5-flash"),
    )
    client = SimpleNamespace(models=FakeModels())

    result = evaluate_offer(
        {"title": "Business Analyst", "job_hash": "offer-hash"},
        {"cv_hash": "cv-hash"},
        [{"section": "Experiencia", "chunk_id": "chunk-1", "text": "Análisis funcional"}],
        client=client,
    )

    assert calls == ["gemini-2.5-flash", FALLBACK_MODEL]
    assert result["model"] == FALLBACK_MODEL
    assert result["evaluation"]["score_match"] == 88
