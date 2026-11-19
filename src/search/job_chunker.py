"""Segmentación de descripciones laborales en fragmentos semánticos."""
from __future__ import annotations

import hashlib
import re

SECTION_RULES = [
    ("responsabilidades", ("responsabilidades", "funciones", "principales tareas", "objetivo del cargo")),
    ("requisitos", ("requisitos", "requerimientos", "requisitos mínimos", "perfil requerido")),
    ("tecnologia", ("tecnologías", "herramientas", "conocimientos técnicos", "software")),
    ("experiencia", ("experiencia", "años de experiencia", "trayectoria")),
    ("condiciones", ("ofrecemos", "condiciones", "beneficios", "jornada", "renta")),
]


def _section(text: str) -> str:
    normalized = text.lower()
    for section, hints in SECTION_RULES:
        if any(hint in normalized for hint in hints):
            return section
    return "general"


def chunk_job_description(title: str, description: str, *, max_chars: int = 1100,
                          overlap_chars: int = 120) -> list[dict]:
    """Crea chunks estables; conserva encabezados y evita fragmentos diminutos."""
    if max_chars < 300 or overlap_chars < 0 or overlap_chars >= max_chars // 2:
        raise ValueError("Parámetros de fragmentación inválidos.")
    source = f"Cargo: {title.strip()}\n\n{description.strip()}".strip()
    if len(source) < 150:
        return []
    paragraphs = [re.sub(r"\\s+", " ", p).strip()
                  for p in re.split(r"\\n+|(?<=[.!?])\\s{2,}", source) if p.strip()]
    chunks, buffer, current_section = [], "", "general"

    def flush():
        nonlocal buffer
        text = buffer.strip()
        if len(text) >= 60:
            digest = hashlib.sha256(f"{current_section}:{text}".encode("utf-8")).hexdigest()[:24]
            chunks.append({"chunk_index": len(chunks), "content": text,
                           "section": current_section, "content_hash": digest})
        buffer = ""

    for paragraph in paragraphs:
        section = _section(paragraph)
        if section != "general" and section != current_section:
            flush()
            current_section = section
        if len(paragraph) > max_chars:
            flush()
            start = 0
            while start < len(paragraph):
                piece = paragraph[start:start + max_chars].strip()
                if len(piece) >= 60:
                    digest = hashlib.sha256(f"{current_section}:{piece}".encode("utf-8")).hexdigest()[:24]
                    chunks.append({"chunk_index": len(chunks), "content": piece,
                                   "section": current_section, "content_hash": digest})
                if start + max_chars >= len(paragraph):
                    break
                start += max_chars - overlap_chars
            continue
        if buffer and len(buffer) + len(paragraph) + 1 > max_chars:
            flush()
        buffer = f"{buffer} {paragraph}".strip()
    flush()
    return chunks
