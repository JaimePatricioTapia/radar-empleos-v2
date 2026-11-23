import json
from types import SimpleNamespace

from src.evaluation import evaluator


def test_evaluator_retries_google_429(monkeypatch):
    attempts = []
    waits = []

    result = {
        "score_match": 85,
        "verdict": "POSTULAR",
        "role_detected": "Business Analyst",
        "strengths": ["Análisis funcional"],
        "gaps": [],
        "hard_constraints": [],
        "evidence": [],
        "uncertainty_notes": [],
        "salary_assessment": "No informada",
        "cv_focus_recommendation": "Destacar experiencia BA",
        "ats_keywords": ["Business Analyst"],
    }

    class FakeModels:
        def generate_content(self, **kwargs):
            attempts.append(kwargs)
            if len(attempts) == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED retry in 0.5s")
            return SimpleNamespace(text=json.dumps(result))

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(
        evaluator,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="fake",
            gemini_model="gemini-2.5-flash",
        ),
    )
    monkeypatch.setattr(evaluator.genai, "Client", FakeClient)
    monkeypatch.setattr(evaluator, "load_system_prompt", lambda: "test prompt")
    monkeypatch.setattr(evaluator.time, "sleep", waits.append)

    run = evaluator.evaluate_offer(
        {"title": "Business Analyst", "description": "Requisitos del cargo"},
        {"cv_hash": "cv-hash"},
        [{"chunk_id": "chunk-1", "section": "experiencia", "text": "Análisis funcional"}],
    )

    assert run["evaluation"]["score_match"] == 85
    assert len(attempts) == 2
    assert waits == [0.5]
