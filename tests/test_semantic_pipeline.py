from src.search.job_chunker import chunk_job_description
from src.search.processing import _excluded_reason, _priority_score, classify_sector
from src.search.sources import canonical_job_url, normalize_offer


def test_job_chunks_are_bounded_and_have_stable_indexes():
    description = ("Responsabilidades\n" + ("Gestionar proyectos y procesos operacionales. " * 90)
                   + "\nRequisitos\n" + ("Experiencia en análisis funcional y sistemas. " * 50))
    chunks = chunk_job_description("Analista Funcional", description)
    assert len(chunks) >= 3
    assert [item["chunk_index"] for item in chunks] == list(range(len(chunks)))
    assert all(60 <= len(item["content"]) <= 1100 for item in chunks)


def test_indeed_job_id_is_preserved_while_tracking_is_removed():
    first = canonical_job_url("https://cl.indeed.com/viewjob?jk=aaa&utm_source=mail")
    second = canonical_job_url("https://cl.indeed.com/viewjob?jk=bbb&utm_source=mail")
    same = canonical_job_url("https://cl.indeed.com/viewjob?utm_campaign=x&jk=aaa")
    assert first != second
    assert first == same


def test_normalized_indeed_offers_do_not_collapse_to_one_hash():
    a = normalize_offer(source="indeed", title="Analista A",
                        url="https://cl.indeed.com/viewjob?jk=aaa", description="x" * 200)
    b = normalize_offer(source="indeed", title="Analista B",
                        url="https://cl.indeed.com/viewjob?jk=bbb", description="x" * 200)
    assert a["job_hash"] != b["job_hash"]


def test_sector_classification_prioritizes_mining_and_supplier():
    assert classify_sector({"title": "Analista Funcional", "company": "Codelco"}) == "MINERIA"
    assert classify_sector({"title": "Project Manager", "company": "Finning",
                            "description": "Servicios y equipos para minería"}) == "PROVEEDOR_MINERO"


def test_priority_is_separate_from_affinity():
    assert _priority_score(90, "MINERIA") == 93
    assert _priority_score(90, "BANCA_FINANZAS") == 81


def test_health_benefit_mention_does_not_exclude_non_health_role():
    offer = {"title": "Analista de Sistemas", "company": "Empresa Tecnológica",
             "description": "Se ofrece seguro complementario de salud y beneficios."}
    assert _excluded_reason(offer) is None
