"""Perfil estructurado de competencias con evidencia trazable del CV.

La extracción es determinística: no inventa años, seniority ni niveles.
"""
from __future__ import annotations

import re
import unicodedata

SKILL_TAXONOMY = [
    ("business_analysis", "Análisis de negocio", "Análisis funcional y negocio", ["business analyst", "analisis de negocio", "analista de negocio"]),
    ("requirements", "Levantamiento de requerimientos", "Análisis funcional y negocio", ["levantamiento de requerimientos", "levantamiento de requisitos", "requerimientos", "requisitos"]),
    ("processes", "Análisis y mejora de procesos", "Análisis funcional y negocio", ["analisis de procesos", "mejora de procesos", "modelamiento de procesos", "procesos de negocio"]),
    ("user_stories", "Historias de usuario y PBI", "Análisis funcional y negocio", ["historias de usuario", "pbi", "product backlog"]),
    ("stakeholders", "Gestión de stakeholders", "Análisis funcional y negocio", ["stakeholders", "usuarios clave", "interesados"]),
    ("project_management", "Gestión de proyectos", "Proyectos y transformación TI", ["gestion de proyectos", "jefe de proyectos", "project manager", "planificacion de proyectos"]),
    ("digital_transformation", "Transformación digital", "Proyectos y transformación TI", ["transformacion digital", "digitalizacion"]),
    ("devops", "Prácticas DevOps", "Proyectos y transformación TI", ["devops", "pipeline", "integracion continua", "despliegue continuo"]),
    ("jira", "Jira", "Herramientas y plataformas", ["jira"]),
    ("confluence", "Confluence", "Herramientas y plataformas", ["confluence"]),
    ("miro", "Miro", "Herramientas y plataformas", ["miro"]),
    ("scrum", "Scrum", "Métodos de trabajo", ["scrum"]),
    ("kanban", "Kanban", "Métodos de trabajo", ["kanban"]),
    ("nexus", "Nexus", "Métodos de trabajo", ["nexus"]),
    ("tech_risk", "Riesgo tecnológico", "Riesgo y seguridad TI", ["riesgo tecnologico", "riesgos tecnologicos"]),
    ("cybersecurity", "Seguridad de la información", "Riesgo y seguridad TI", ["seguridad de la informacion", "ciberseguridad", "seguridad informatica"]),
    ("ethical_hacking", "Ethical hacking", "Riesgo y seguridad TI", ["ethical hacking", "hacking etico"]),
    ("fraud", "Prevención de fraude digital", "Riesgo y seguridad TI", ["prevencion de fraude", "fraude digital", "biocatch", "getscore"]),
    ("sql", "SQL", "Datos y analítica", ["sql", "sql server"]),
    ("power_query", "Power Query", "Datos y analítica", ["power query"]),
    ("power_bi", "Power BI", "Datos y analítica", ["power bi"]),
    ("big_data", "Big Data", "Datos y analítica", ["big data", "ciencia de datos"]),
    ("rstudio", "RStudio / R", "Datos y analítica", ["rstudio", "r studio", "r programming", "lenguaje r"]),
    ("colab", "Google Colab", "Datos y analítica", ["google colab", "colab"]),
    ("mining_operations", "Operaciones mineras", "Minería y operaciones", ["operaciones mineras", "operaciones mina", "faena minera"]),
    ("raise_boring", "Raise Boring", "Minería y operaciones", ["raise boring", "raise borer"]),
    ("mining_processes", "Procesos mineros", "Minería y operaciones", ["procesos mineros", "procesamiento de minerales"]),
    ("continuity", "Continuidad operacional", "Minería y operaciones", ["continuidad operacional", "continuidad operativa"]),
    ("codelco", "Experiencia en faenas Codelco", "Minería y operaciones", ["codelco", "chuquicamata", "el teniente"]),
    ("digital_channels", "Canales y productos digitales", "Producto digital", ["canales digitales", "app personas", "banca digital", "producto digital"]),
    ("backlog_prioritization", "Priorización de backlog", "Producto digital", ["priorizacion de backlog", "gestion de backlog", "backlog"]),
]

LEVEL_PATTERNS = [
    ("básico", re.compile(r"\b(basico|basica|nivel basico)\b")),
    ("intermedio", re.compile(r"\b(intermedio|intermedia|nivel intermedio)\b")),
    ("avanzado", re.compile(r"\b(avanzado|avanzada|nivel avanzado)\b")),
    ("experto", re.compile(r"\b(experto|experta)\b")),
]


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)


def _evidence_excerpt(text: str, term: str, radius: int = 110) -> str:
    normalized, needle = _normalise(text), _normalise(term)
    position = normalized.find(needle)
    if position < 0:
        return text[: min(len(text), radius * 2)].strip()
    start, end = max(0, position - radius), min(len(text), position + len(term) + radius)
    excerpt = text[start:end].strip()
    return ("…" if start else "") + excerpt + ("…" if end < len(text) else "")


def _declared_level(text: str, term: str) -> str:
    normalized, needle = _normalise(text), _normalise(term)
    position = normalized.find(needle)
    if position < 0:
        return "no_declarado"
    term_end = position + len(needle)
    context_start = max(0, position - 24)
    context_end = min(len(normalized), term_end + 24)
    context = normalized[context_start:context_end]
    candidates = []
    for label, pattern in LEVEL_PATTERNS:
        for match in pattern.finditer(context):
            absolute_start = context_start + match.start()
            absolute_end = context_start + match.end()
            distance = min(abs(absolute_start - term_end), abs(position - absolute_end))
            if distance <= 22:
                candidates.append((distance, label))
    return min(candidates, default=(None, "no_declarado"))[1]


def derive_skills_profile(chunks: list[dict] | list[str]) -> dict:
    """Devuelve competencias encontradas con fragmento, sección y nivel declarado."""
    records = []
    for index, item in enumerate(chunks):
        if isinstance(item, str):
            records.append({"chunk_id": str(index), "section": "general", "content": item})
        else:
            records.append({
                "chunk_id": str(item.get("chunk_id") or index),
                "section": str(item.get("section") or "general"),
                "content": str(item.get("content") or item.get("text") or ""),
            })
    skills = []
    for skill_id, label, category, terms in SKILL_TAXONOMY:
        evidence = []
        declared_levels = []
        for chunk in records:
            content = chunk["content"]
            normalized = _normalise(content)
            matched = next((term for term in terms if _normalise(term) in normalized), None)
            if not matched:
                continue
            evidence.append({
                "chunk_id": chunk["chunk_id"],
                "section": chunk["section"],
                "matched_term": matched,
                "excerpt": _evidence_excerpt(content, matched),
            })
            level = _declared_level(content, matched)
            if level != "no_declarado":
                declared_levels.append(level)
        if evidence:
            skills.append({
                "id": skill_id,
                "name": label,
                "category": category,
                "evidence_count": len(evidence),
                "proficiency": declared_levels[0] if declared_levels else "no_declarado",
                "proficiency_source": "CV" if declared_levels else None,
                "evidence": evidence[:5],
            })
    categories = {}
    for skill in skills:
        categories[skill["category"]] = categories.get(skill["category"], 0) + 1
    return {
        "skills": skills,
        "skill_count": len(skills),
        "categories": categories,
        "method": "deterministic_evidence_taxonomy_v1",
        "limitations": [
            "La presencia de una competencia no demuestra por sí sola dominio o años de experiencia.",
            "El nivel solo se informa cuando aparece explícitamente cerca de la competencia en el CV.",
            "Las coincidencias deben ser revisadas por la persona antes de usarse como afirmaciones en una postulación.",
        ],
    }
