"""Lectura conservadora de renta para preferencias laborales en Chile.

No convierte renta bruta a líquida ni descarta ofertas por remuneración.
"""
from __future__ import annotations

import re
import unicodedata

PREFERRED_MINIMUM_CLP = 1_000_000


def _normalise(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _amounts(text: str) -> list[int]:
    value = _normalise(text)
    found: list[int] = []
    for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:millones?|mm)\b", value):
        number = float(match.group(1).replace(".", "").replace(",", "."))
        found.append(int(number * 1_000_000))
    for match in re.finditer(r"(?:\$\s*|\bclp\s*)(\d{1,3}(?:[.\s]\d{3}){1,2}|\d{5,9})\b", value):
        number = int(re.sub(r"[.\s]", "", match.group(1)))
        if number >= 100_000:
            found.append(number)
    # Formato frecuente sin símbolo: 1.200.000 líquidos.
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\.\d{3}){1,2})(?!\d)", value):
        number = int(match.group(1).replace(".", ""))
        if number >= 100_000:
            found.append(number)
    return sorted(set(found))


def analyse_salary(salary_text: str | None) -> dict:
    """Clasifica renta sin asumir equivalencia entre bruto y líquido."""
    raw = str(salary_text or "").strip()
    if not raw:
        return {
            "status": "unknown", "basis": "unknown", "minimum_clp": None,
            "maximum_clp": None, "adjustment": 0,
            "label": "Renta no informada; no se aplica penalización.",
        }
    text = _normalise(raw)
    amounts = _amounts(raw)
    if not amounts:
        return {
            "status": "unknown", "basis": "unknown", "minimum_clp": None,
            "maximum_clp": None, "adjustment": 0,
            "label": "Renta informada sin monto comparable; no se aplica penalización.",
        }
    if any(term in text for term in ("bruto", "bruta", "imponible", "antes de impuesto")):
        return {
            "status": "not_comparable", "basis": "gross",
            "minimum_clp": min(amounts), "maximum_clp": max(amounts),
            "adjustment": 0,
            "label": "Renta bruta/imponible; no se compara con el mínimo líquido.",
        }
    if not any(term in text for term in ("liquido", "liquida", "despues de impuesto", "a pago")):
        return {
            "status": "not_comparable", "basis": "unspecified",
            "minimum_clp": min(amounts), "maximum_clp": max(amounts),
            "adjustment": 0,
            "label": "Monto sin indicar si es líquido; no se aplica penalización.",
        }
    low, high = min(amounts), max(amounts)
    if high < PREFERRED_MINIMUM_CLP:
        status, adjustment = "below_preference", -10
        label = "Renta líquida inferior a $1.000.000; reduce el atractivo, no la elegibilidad."
    elif low < PREFERRED_MINIMUM_CLP <= high:
        status, adjustment = "range_crosses_preference", -5
        label = "El rango líquido cruza $1.000.000; se aplica una penalización moderada."
    else:
        status, adjustment = "meets_preference", 0
        label = "Renta líquida desde $1.000.000; cumple la preferencia."
    return {
        "status": status, "basis": "net", "minimum_clp": low,
        "maximum_clp": high, "adjustment": adjustment, "label": label,
    }


def attractiveness_score(affinity: int, salary_analysis: dict) -> int:
    """Indicador provisional: afinidad menos ajuste por renta, sin descartes."""
    adjustment = int(salary_analysis.get("adjustment", 0) or 0)
    return max(0, min(100, int(affinity) + adjustment))
