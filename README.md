# Radar de Empleos 2.0

Nueva versión independiente del Radar de Empleos. Este repositorio no modifica ni despliega cambios en `radar-empleos-jptn`.

## Objetivos

1. Mantener una fuente de verdad del CV con hash SHA-256 y versionamiento.
2. Segmentar CV y ofertas en chunks y generar embeddings.
3. Recuperar evidencia pertinente mediante Gemini + pgvector.
4. Evaluar ofertas con Gemini, evidencia trazable y restricciones determinísticas.
5. Construir un benchmark reproducible de ofertas revisadas por una persona.
6. Mantener la base de datos de desarrollo separada de cualquier entorno productivo.

## Estado de implementación

- Lector de CV, hash, chunker y manifiesto: base implementada.
- Adaptador de embeddings Gemini con dimensión fija 3.072: implementado, pendiente prueba real de API.
- Esquema SQL de Supabase con pgvector, RLS y búsqueda HNSW: escrito, pendiente aplicar y validar en un proyecto de desarrollo.
- Repositorio de persistencia de CV/ofertas/evaluaciones: primera versión implementada.
- Recuperación semántica de evidencia CV: primera versión implementada.
- Autenticación de usuario en la interfaz Streamlit, orquestación transaccional y migración de la ingesta: pendientes.
- Benchmark de 50 ofertas y comparación de modelos/prompts: pendientes.

## Inicio local

1. Crear entorno virtual: `python -m venv .venv`.
2. Activarlo e instalar dependencias: `pip install -r requirements.txt`.
3. Copiar `.env.example` a `.env` y completar las credenciales.
4. Configurar `CV_PDF_PATH` con la ruta local del CV. El PDF debe permanecer fuera de Git.
5. Ejecutar pruebas: `pytest -q`.

## Supabase

Revisar `supabase/README.md` y `supabase/schema.sql`. El SQL está preparado para un proyecto independiente de desarrollo; todavía no ha sido aplicado a ninguna base.

## Seguridad

- Este repositorio debe permanecer privado.
- No versionar CV, postulaciones, cachés, archivos `.env`, service-role keys ni sesiones.
- La base Supabase de desarrollo debe ser distinta de la productiva.
- No ejecutar este esquema en producción.
- La app debe operar con sesión autenticada y políticas RLS; nunca exponer una clave privilegiada en el cliente.

## Principio de evaluación

Los embeddings ayudan a recuperar fragmentos relevantes; **no determinan por sí solos la compatibilidad ni el veredicto**. La evaluación final combina evidencia recuperada, reglas explícitas, perfil estructurado y Gemini. El benchmark humano será la referencia para medir calidad.
