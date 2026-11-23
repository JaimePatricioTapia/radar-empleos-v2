"""Deriva familias de búsqueda desde evidencia textual del CV activo.

Extracción local y determinística: no llama a modelos, APIs ni embeddings.
"""
from __future__ import annotations

import re
import unicodedata


FAMILY_RULES = [
    {
        "id": "business_analysis",
        "name": "Análisis de negocio y procesos",
        "priority": 1,
        "evidence_terms": ["business analyst", "analista de negocio", "analista funcional",
            "requerimientos", "levantamiento", "historias de usuario", "procesos", "stakeholders", "pbi"],
        "titles": ["Business Analyst", "Analista Funcional"],
        "domain_terms": ["requerimientos", "procesos", "historias de usuario"],
    },
    {
        "id": "it_projects",
        "name": "Proyectos y transformación TI",
        "priority": 1,
        "evidence_terms": ["jefe de proyectos", "project manager", "gestion de proyectos",
            "proyectos ti", "transformacion digital", "devops", "planificacion", "coordinacion"],
        "titles": ["Jefe de Proyectos TI", "Project Manager TI"],
        "domain_terms": ["proyectos TI", "transformacion digital", "DevOps"],
    },
    {
        "id": "mining_technology",
        "name": "Tecnología minera y operaciones",
        "priority": 1,
        "evidence_terms": ["mineria", "minero", "codelco", "raise boring", "master drilling",
            "procesos mineros", "operaciones", "chuquicamata", "el teniente", "sondaje"],
        "titles": ["Analista TI Minería", "Especialista Sistemas Mineros"],
        "domain_terms": ["minería", "sistemas mineros", "operaciones"],
    },
    {
        "id": "technology_risk",
        "name": "Riesgo tecnológico y seguridad TI",
        "priority": 2,
        "evidence_terms": ["riesgo tecnologico", "ethical hacking", "seguridad", "biocatch",
            "gets core", "getscore", "ciberseguridad", "fraude"],
        "titles": ["Analista de Riesgo Tecnológico", "Analista de Seguridad TI"],
        "domain_terms": ["riesgo tecnológico", "seguridad TI", "prevención de fraude"],
    },
    {
        "id": "data_analytics",
        "name": "Datos y analítica",
        "priority": 2,
        "evidence_terms": ["big data", "ciencia de datos", "sql", "power query",
            "power bi", "analisis de datos", "analitica", "r studio", "rstudio"],
        "titles": ["Analista de Datos", "Analista BI"],
        "domain_terms": ["SQL", "Big Data", "analítica"],
    },
    {
        "id": "digital_product",
        "name": "Producto digital",
        "priority": 2,
        "evidence_terms": ["product owner", "producto digital", "backlog", "priorizacion",
            "roadmap", "app personas", "banca digital", "experiencia clientes"],
        "titles": ["Product Owner", "Analista de Producto Digital"],
        "domain_terms": ["producto digital", "backlog", "banca digital"],
    },
]

EXCLUDED_TITLE_TERMS = ("scrum master",)
MAX_GENERATED_TITLES = 12


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)


def derive_role_families(cv_chunks: list[dict] | list[str]) -> dict:
    """Retorna familias sustentadas, términos coincidentes y títulos acotados."""
    text = " ".join(
        item if isinstance(item, str) else str(item.get("content") or item.get("text") or "")
        for item in cv_chunks
    )
    normalized = _normalize(text)
    families = []
    for rule in FAMILY_RULES:
        matched = [term for term in rule["evidence_terms"] if _normalize(term) in normalized]
        # Dos señales independientes reducen falsos positivos por una palabra aislada.
        if len(matched) < 2:
            continue
        titles = [
            title for title in rule["titles"]
            if not any(excluded in _normalize(title) for excluded in EXCLUDED_TITLE_TERMS)
        ]
        families.append({
            "id": rule["id"],
            "name": rule["name"],
            "priority": rule["priority"],
            "titles": titles,
            "domain_terms": rule["domain_terms"],
            "evidence": matched,
        })
    families.sort(key=lambda item: (item["priority"], -len(item["evidence"]), item["id"]))
    roles = []
    for family in families:
        for title in family["titles"]:
            if title not in roles and len(roles) < MAX_GENERATED_TITLES:
                roles.append(title)
    return {
        "families": families,
        "roles": roles,
        "evidence_count": sum(len(item["evidence"]) for item in families),
        "method": "deterministic_cv_evidence_v1",
    }
