"""Lectura dinámica y versionamiento del CV maestro; nunca guarda el PDF en Git."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pypdf import PdfReader


def read_cv(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"No se encontró un PDF válido en: {path}")

    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(part.strip() for part in pages if part.strip())
    if not text:
        raise ValueError("El PDF no contiene texto extraíble; podría requerir OCR.")

    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return {
        "text": text,
        "cv_hash": digest,
        "filename": path.name,
        "page_count": len(reader.pages),
        "character_count": len(text),
        "file_modified_at": modified.isoformat(),
        "read_at": datetime.now(timezone.utc).isoformat(),
    }
