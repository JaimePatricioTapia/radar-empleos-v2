"""Segmentación determinística inicial del CV en fragmentos con metadatos.

La primera versión usa encabezados y párrafos; posteriormente se podrá afinar
con estructura específica del CV y revisión visual de fragmentos.
"""
from __future__ import annotations
import hashlib
from typing import Any

SECTION_HINTS = {
    "experiencia": ("experiencia", "trayectoria", "experiencia laboral"),
    "formacion": ("formación", "educación", "estudios", "formación académica"),
    "competencias": ("competencias", "habilidades", "conocimientos"),
    "certificaciones": ("certificaciones", "cursos", "diplomados"),
}


def _section_for_heading(text: str) -> str:
    normalized = text.lower().strip(" :\t")
    for section, hints in SECTION_HINTS.items():
        if any(hint in normalized for hint in hints):
            return section
    return "general"


def chunk_cv(cv_text: str, cv_hash: str, max_chars: int = 1200) -> list[dict[str, Any]]:
    if max_chars < 200:
        raise ValueError("max_chars debe ser al menos 200.")
    chunks: list[dict[str, Any]] = []
    current_section = "general"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        joined = "\n".join(buffer).strip()
        if not joined:
            buffer = []
            return
        # Dividir párrafos largos sin cortar palabras.
        pieces: list[str] = []
        remaining = joined
        while len(remaining) > max_chars:
            cut = remaining.rfind(" ", 0, max_chars + 1)
            if cut < max_chars // 2:
                cut = max_chars
            pieces.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            pieces.append(remaining)
        for piece in pieces:
            if not piece:
                continue
            digest = hashlib.sha256(f"{cv_hash}:{current_section}:{piece}".encode()).hexdigest()[:20]
            chunks.append({
                "chunk_id": digest,
                "cv_hash": cv_hash,
                "section": current_section,
                "text": piece,
                "char_count": len(piece),
            })
        buffer = []

    for line in cv_text.splitlines():
        clean = line.strip()
        if not clean:
            if buffer and sum(map(len, buffer)) >= max_chars * 0.65:
                flush()
            continue
        candidate_section = _section_for_heading(clean)
        looks_like_heading = len(clean) <= 70 and (clean.isupper() or candidate_section != "general")
        if looks_like_heading:
            flush()
            current_section = candidate_section
            buffer.append(clean)
        else:
            if buffer and sum(map(len, buffer)) + len(clean) + 1 > max_chars:
                flush()
            buffer.append(clean)
    flush()
    return chunks
