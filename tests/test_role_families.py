from src.search.role_families import derive_role_families


def test_cv_evidence_generates_multiple_functional_families():
    chunks = [
        {"content": "Business Analyst, levantamiento de requerimientos, historias de usuario y procesos."},
        {"content": "Ingeniero en minería, Codelco, operaciones en Chuquicamata y Raise Boring."},
        {"content": "Big Data, Ciencia de Datos, SQL y Power Query."},
    ]
    profile = derive_role_families(chunks)
    ids = {family["id"] for family in profile["families"]}
    assert {"business_analysis", "mining_technology", "data_analytics"} <= ids
    assert "Business Analyst" in profile["roles"]
    assert "Analista TI Minería" in profile["roles"]


def test_single_weak_keyword_does_not_activate_family():
    profile = derive_role_families(["Tengo conocimientos básicos de SQL."])
    assert "data_analytics" not in {family["id"] for family in profile["families"]}


def test_scrum_master_is_never_generated_as_target():
    profile = derive_role_families([
        "Scrum Master, Business Analyst, procesos, requerimientos, gestión de proyectos."
    ])
    assert all("scrum master" not in role.lower() for role in profile["roles"])


def test_profile_is_deterministic_and_does_not_call_external_services():
    chunks = ["Product Owner, backlog, priorización, banca digital, app personas."]
    assert derive_role_families(chunks) == derive_role_families(chunks)
