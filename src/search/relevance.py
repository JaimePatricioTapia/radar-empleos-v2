"""Filtro determinístico de pertinencia laboral antes de persistir ofertas.

No descarta por sector ni consume APIs: busca señales funcionales relacionadas
con los objetivos de Radar y bloquea ocupaciones claramente ajenas cuando no
existe evidencia técnica/funcional suficiente en la descripción.
"""
from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Señales del título: cargos objetivos y funciones equivalentes/adicionales.
TITLE_SIGNALS = (
    "business analyst", "business analysis", "analista de negocio",
    "analista funcional", "analista ti", "analista de sistemas",
    "analista de procesos", "analista de proyectos", "analista de datos",
    "analista bi", "analista de riesgo", "analista de seguridad",
    "analista de producto", "product owner", "product manager",
    "project manager", "jefe de proyectos", "gerente de proyectos",
    "coordinador de proyectos", "administrador de proyectos",
    "pmo", "transformacion digital", "tecnologia minera",
    "sistemas mineros", "especialista ti", "especialista tecnologia",
    "especialista en tecnologia", "especialista en sistemas",
    "ingeniero de sistemas", "ingeniero de proyectos ti",
    "ingeniero de procesos", "ciberseguridad", "riesgo tecnologico",
    "automatizacion de procesos", "gobierno de datos",
)

# Una ocupación ajena solo se bloquea si el título no tiene una señal objetivo
# y la descripción tampoco demuestra una función tecnológica/analítica relevante.
UNRELATED_TITLE_SIGNALS = (
    "conserje", "bodeguero", "bodeguera", "repartidor", "repartidora",
    "vendedor", "vendedora", "promotor", "promotora", "cajero", "cajera",
    "reponedor", "reponedora", "guardia de seguridad", "asesora de ventas",
    "asesor de ventas", "ejecutivo comercial", "ejecutiva comercial",
    "asistente comercial", "convivencia escolar", "inspector de patio",
    "auxiliar de aseo", "operario de produccion", "operaria de produccion",
    "maestro de cocina", "garzon", "garzona", "chofer", "conductor",
    "tecnico en enfermeria", "enfermero", "enfermera", "medico", "medica",
    "docente", "profesor", "profesora", "educadora de parvulos",
)

DESCRIPTION_SIGNALS = (
    "levantamiento de requerimientos", "levantamiento de requisitos",
    "historias de usuario", "analisis funcional", "analisis de negocio",
    "business analyst", "gestion de proyectos", "proyectos ti",
    "transformacion digital", "implementacion de sistemas",
    "mejora de procesos", "modelamiento de procesos", "procesos de negocio",
    "product owner", "product manager", "gestion de backlog",
    "priorizacion de backlog", "roadmap de producto", "analisis de datos",
    "inteligencia de negocios", "business intelligence", "power bi",
    "power query", "big data", "ciencia de datos", "sql",
    "riesgo tecnologico", "ciberseguridad", "seguridad de la informacion",
    "ethical hacking", "fraude digital", "sistemas mineros",
    "tecnologia minera", "operaciones mineras", "mineria",
    "automatizacion", "devops", "jira", "sap", "stakeholders",
)

TECHNICAL_DESCRIPTION_SIGNALS = (
    "requerimientos", "requisitos", "historias de usuario",
    "analisis funcional", "analisis de negocio", "proyectos ti",
    "transformacion digital", "sistemas", "procesos de negocio",
    "product owner", "product manager", "backlog", "roadmap",
    "inteligencia de negocios", "business intelligence", "power bi",
    "power query", "big data", "ciencia de datos", "sql",
    "riesgo tecnologico", "ciberseguridad", "seguridad de la informacion",
    "ethical hacking", "sistemas mineros", "tecnologia minera",
    "operaciones mineras", "automatizacion", "devops", "jira",
)


def assess_offer_relevance(offer: dict) -> tuple[bool, str]:
    """Devuelve (aceptar, explicación); los casos dudosos se conservan."""
    title = normalize_text(offer.get("title") or "")
    description = normalize_text((offer.get("description") or "")[:8000])

    if any(normalize_text(term) in title for term in TITLE_SIGNALS):
        return True, "cargo objetivo identificado en el título"

    description_hits = [
        term for term in DESCRIPTION_SIGNALS
        if normalize_text(term) in description
    ]
    technical_hits = [
        term for term in TECHNICAL_DESCRIPTION_SIGNALS
        if normalize_text(term) in description
    ]
    if len(set(description_hits)) >= 2 and technical_hits:
        return True, "funciones TI/analíticas identificadas en la descripción"

    unrelated = next(
        (term for term in UNRELATED_TITLE_SIGNALS if normalize_text(term) in title),
        None,
    )
    if unrelated:
        return False, f"ocupación ajena a los objetivos: {unrelated}"

    if not title:
        return False, "aviso sin título identificable"
    if len(description) < 80:
        return False, "sin señales de cargo objetivo ni descripción suficiente"
    return False, "no se identificaron funciones TI, análisis, proyectos, producto o minería"
