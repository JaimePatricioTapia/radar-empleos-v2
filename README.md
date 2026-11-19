# Radar de Empleos 2.0

Nueva versión independiente del Radar de Empleos. Este repositorio no modifica ni despliega cambios en radar-empleos-jptn.

## Objetivos

1. Mantener una fuente de verdad del CV con hash SHA-256 y versionamiento.
2. Segmentar CV y ofertas en chunks y generar embeddings.
3. Recuperar evidencia pertinente mediante Gemini + pgvector.
4. Evaluar ofertas con Gemini, evidencia trazable y restricciones determinísticas.
5. Construir un benchmark reproducible de ofertas revisadas por una persona.
6. Mantener la base de datos de desarrollo separada de cualquier entorno productivo.

## Estado de implementación

- Lector de CV, hash y chunker: implementados.
- Embeddings Gemini de 3.072 dimensiones: adaptador implementado; requiere prueba integrada real.
- Proyecto Supabase independiente Radar Empleos 2.0: esquema aplicado y verificado.
- Persistencia de versiones del CV, fragmentos, ofertas y evaluaciones: implementada.
- Seguridad RLS: habilitada en las seis tablas.
- Recuperación semántica pgvector del CV: implementada.
- Autenticación, ingesta local del CV y evaluación manual: implementadas.
- Etapa 1 — búsqueda automática multifuente: conectores y dashboard implementados en la rama feature/multisource-job-discovery-stage1; pendiente ejecutar pruebas locales y barrido real de portales.
- Etapa siguiente: vectorizar ofertas, recuperación CV ↔ oferta y evaluación automática de nuevas capturas.

## Inicio local

Siga docs/SETUP_LOCAL.md. En resumen: activar el entorno virtual, instalar requirements.txt, completar .env y ejecutar streamlit run app.py.

## Supabase

El esquema reproducible está en supabase/schema.sql. Aplicar SOLO en el proyecto de desarrollo Radar Empleos 2.0, nunca en la base productiva.

## Seguridad

- Mantener el repositorio privado.
- No versionar CV, postulaciones, cachés, archivos .env, service-role keys ni sesiones.
- La app usa sesión autenticada y políticas RLS; nunca exponer una clave privilegiada.
- El PDF original permanece local; no se sube a GitHub ni a Supabase.

## Principio de evaluación

Los embeddings ayudan a recuperar fragmentos relevantes; no determinan por sí solos la compatibilidad ni el veredicto. La evaluación combina evidencia recuperada, restricciones explícitas y Gemini. El benchmark humano será la referencia para medir calidad.
