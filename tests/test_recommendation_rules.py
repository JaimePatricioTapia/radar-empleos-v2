from src.search.processing import (
    MINIMUM_AFFINITY_SCORE,
    _excluded_reason,
    classify_sector,
    meets_affinity_threshold,
)


def test_recommendations_require_at_least_85_percent():
    assert MINIMUM_AFFINITY_SCORE == 85
    assert meets_affinity_threshold(85)
    assert meets_affinity_threshold(100)
    assert not meets_affinity_threshold(84)
    assert not meets_affinity_threshold(None)


def test_mining_company_is_classified_as_mining():
    offer = {
        "title": "Business Analyst",
        "company": "BHP Chile",
        "description": "Gestión de procesos y proyectos tecnológicos.",
    }
    assert classify_sector(offer) == "MINERIA"


def test_mining_supplier_is_classified_as_mining_supplier():
    offer = {
        "title": "Ingeniero de Proyectos",
        "company": "Finning",
        "description": "Soporte de equipos y servicios para operaciones mineras.",
    }
    assert classify_sector(offer) == "PROVEEDOR_MINERO"


def test_mining_in_description_is_not_lost_when_title_is_generic():
    offer = {
        "title": "Analista de Procesos",
        "company": "Consultora",
        "description": "El cargo apoyará operaciones mineras, faenas y plantas concentradoras.",
    }
    assert classify_sector(offer) == "MINERIA"


def test_professional_internship_is_excluded():
    offer = {
        "title": "Práctica Ing Civil Mecánica o carrera afín",
        "company": "Empresa industrial",
    }
    assert _excluded_reason(offer) is not None


def test_occupational_safety_specialty_is_excluded():
    offer = {
        "title": "Ingeniero Prevencionista con Diplomado en Higiene Ocupacional",
        "company": "Empresa minera",
    }
    assert _excluded_reason(offer) is not None
