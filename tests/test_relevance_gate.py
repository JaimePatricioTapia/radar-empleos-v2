from src.search.relevance import assess_offer_relevance


def test_rejects_obviously_unrelated_titles_without_relevant_description():
    titles = [
        "Se requiere conserjes 4x4",
        "Bodeguero / repartidor licencia B",
        "Vendedor Mall Sport",
        "Coordinador de Convivencia",
        "Asistente Comercial y Administración",
    ]
    for title in titles:
        accepted, reason = assess_offer_relevance({"title": title, "description": title})
        assert not accepted, title
        assert reason


def test_accepts_core_target_roles_by_title():
    titles = [
        "Business Analyst Senior",
        "Analista Funcional TI",
        "Jefe de Proyectos TI",
        "Product Owner",
        "Analista de Riesgo Tecnológico",
        "Analista de Datos",
        "Especialista Sistemas Mineros",
    ]
    for title in titles:
        accepted, _ = assess_offer_relevance({"title": title, "description": ""})
        assert accepted, title


def test_accepts_adjacent_title_when_description_has_multiple_strong_signals():
    offer = {
        "title": "Coordinador de Implementación",
        "description": (
            "Responsable del levantamiento de requerimientos, historias de usuario, "
            "gestión de proyectos TI e implementación de sistemas para áreas usuarias."
        ),
    }
    accepted, _ = assess_offer_relevance(offer)
    assert accepted


def test_keeps_relevant_role_even_if_title_has_a_broad_word():
    offer = {
        "title": "Coordinador de Proyectos TI",
        "description": "Coordinación de proyectos y seguimiento de hitos.",
    }
    accepted, _ = assess_offer_relevance(offer)
    assert accepted


def test_does_not_accept_generic_description_without_domain_evidence():
    offer = {
        "title": "Asistente Administrativo",
        "description": "Apoyar gestión, coordinación, documentación y tareas administrativas.",
    }
    accepted, _ = assess_offer_relevance(offer)
    assert not accepted
