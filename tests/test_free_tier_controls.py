from src.search.processing import (
    MAX_DAILY_EVALUATIONS,
    MAX_DAILY_JOB_CHUNKS,
    _local_relevance_score,
)


def test_free_tier_budgets_are_conservative_and_finite():
    assert MAX_DAILY_JOB_CHUNKS == 250
    assert MAX_DAILY_EVALUATIONS == 15


def test_local_prefilter_prioritizes_mining_business_analysis_without_gemini():
    mining_offer = {
        "title": "Business Analyst Minería",
        "company": "Proveedor minero",
        "description": "Levantamiento de requisitos y gestión de proyectos para faena minera.",
    }
    generic_offer = {
        "title": "Asistente administrativo",
        "company": "Empresa de servicios",
        "description": "Apoyo administrativo general y tareas de oficina.",
    }
    assert _local_relevance_score(mining_offer) > _local_relevance_score(generic_offer)
