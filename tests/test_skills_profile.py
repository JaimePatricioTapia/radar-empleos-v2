from src.cv.skills_profile import derive_skills_profile


def test_skill_profile_keeps_traceable_evidence_and_declared_level():
    profile = derive_skills_profile([
        {
            "chunk_id": "cv-1",
            "section": "Competencias",
            "content": "SQL intermedio, Power BI básico y levantamiento de requerimientos.",
        }
    ])
    by_id = {item["id"]: item for item in profile["skills"]}
    assert by_id["sql"]["proficiency"] == "intermedio"
    assert by_id["power_bi"]["proficiency"] == "básico"
    assert by_id["requirements"]["evidence"][0]["chunk_id"] == "cv-1"
    assert "levantamiento de requerimientos" in by_id["requirements"]["evidence"][0]["excerpt"]


def test_skill_profile_does_not_invent_proficiency_or_years():
    profile = derive_skills_profile([
        {"chunk_id": "cv-2", "section": "Experiencia", "content": "Gestión de proyectos y uso de Jira."}
    ])
    by_id = {item["id"]: item for item in profile["skills"]}
    assert by_id["project_management"]["proficiency"] == "no_declarado"
    assert "years" not in by_id["project_management"]
    assert profile["method"] == "deterministic_evidence_taxonomy_v1"


def test_skill_profile_ignores_terms_not_present_in_cv():
    profile = derive_skills_profile(["Experiencia en operaciones mineras y Raise Boring."])
    ids = {item["id"] for item in profile["skills"]}
    assert "raise_boring" in ids
    assert "power_bi" not in ids
