"""Esquemas Pydantic de evaluación, con trazabilidad de evidencia."""
from typing import Literal
from pydantic import BaseModel, Field

class EvidenceItem(BaseModel):
    requirement: str
    cv_evidence: str = Field(description="Cita o resumen fiel de evidencia presente en el CV.")
    status: Literal["cumple", "parcial", "no_cumple", "no_evaluable"]
    importance: Literal["obligatorio", "deseable", "contextual"]

class OfferEvaluation(BaseModel):
    score_match: int = Field(ge=0, le=100)
    verdict: Literal["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"]
    role_detected: str
    strengths: list[str]
    gaps: list[str]
    hard_constraints: list[str]
    evidence: list[EvidenceItem]
    uncertainty_notes: list[str]
    salary_assessment: str
    cv_focus_recommendation: str
    ats_keywords: list[str]
