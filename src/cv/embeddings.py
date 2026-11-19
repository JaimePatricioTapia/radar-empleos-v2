"""Adaptador Gemini para generar embeddings de chunks del CV.

No persiste vectores todavía: primero validamos generación, dimensiones y
versionado del modelo; la persistencia pgvector se incorpora en una migración
separada de Supabase de desarrollo.
"""
from __future__ import annotations
from typing import Any
from google import genai


def embed_texts(texts: list[str], api_key: str, model: str = "gemini-embedding-001") -> list[list[float]]:
    if not texts:
        return []
    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []
    for text in texts:
        response: Any = client.models.embed_content(model=model, contents=text)
        embedding = getattr(response, "embeddings", None)
        if not embedding:
            raise RuntimeError("Gemini no devolvió un embedding para uno de los fragmentos.")
        vector = list(embedding[0].values)
        if not vector:
            raise RuntimeError("Gemini devolvió un embedding vacío.")
        vectors.append(vector)
    return vectors
