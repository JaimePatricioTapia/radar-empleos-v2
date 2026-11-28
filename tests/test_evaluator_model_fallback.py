import json
from types import SimpleNamespace

import pytest

from src.evaluation.evaluator import (
    MODEL_PRIORITY,
    GeminiEvaluationDeferred,
    _daily_quota_retry_seconds,
    evaluate_offer,
)


VALID_RESULT = {
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
}


def _run_evaluation(client, monkeypatch):
    monkeypatch.setattr("src.evaluation.evaluator.get_settings",
                        lambda: SimpleNamespace(gemini_api_key="fake"))
    monkeypatch.setattr("src.evaluation.evaluator.load_system_prompt", lambda: "test prompt")
    return evaluate_offer(
        {"title": "Business Analyst", "job_hash": "offer-hash"},
        {"cv_hash": "cv-hash"},
        [{"section": "Experiencia", "chunk_id": "chunk-1", "text": "Análisis funcional"}],
        client=client,
    )


def test_model_priority_is_exactly_the_requested_order():
    assert MODEL_PRIORITY == (
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
    )


def test_evaluator_uses_first_model_when_it_is_available(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            return SimpleNamespace(text=json.dumps(VALID_RESULT))

    run = _run_evaluation(SimpleNamespace(models=FakeModels()), monkeypatch)

    assert calls == [MODEL_PRIORITY[0]]
    assert run["model"] == MODEL_PRIORITY[0]


def test_evaluator_falls_back_in_priority_order_when_model_is_unavailable(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            if len(calls) < 3:
                raise RuntimeError("404 NOT_FOUND: model is not available")
            return SimpleNamespace(text=json.dumps(VALID_RESULT))

    run = _run_evaluation(SimpleNamespace(models=FakeModels()), monkeypatch)

    assert calls == list(MODEL_PRIORITY[:3])
    assert run["model"] == MODEL_PRIORITY[2]


def test_evaluator_uses_next_model_when_daily_quota_is_exhausted(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            if len(calls) == 1:
                raise RuntimeError(
                    "Generate content requests per day limit exceeded. Please retry in 22h9m16s."
                )
            return SimpleNamespace(text=json.dumps(VALID_RESULT))

    run = _run_evaluation(SimpleNamespace(models=FakeModels()), monkeypatch)

    assert calls == list(MODEL_PRIORITY[:2])
    assert run["model"] == MODEL_PRIORITY[1]


def test_evaluator_defers_only_after_all_models_hit_daily_quota(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            raise RuntimeError(
                "Generate content requests per day limit exceeded. Please retry in 12h0m0s."
            )

    with pytest.raises(GeminiEvaluationDeferred) as error:
        _run_evaluation(SimpleNamespace(models=FakeModels()), monkeypatch)

    assert calls == list(MODEL_PRIORITY)
    assert error.value.retry_after_seconds == 12 * 3600
    assert "cuotas" in str(error.value)


def test_daily_quota_without_retry_duration_uses_safe_24h_pause():
    assert _daily_quota_retry_seconds(
        "GenerateRequestsPerDayPerModel-FreeTier quota exceeded"
    ) == 24 * 3600
