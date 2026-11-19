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

- Lector de CV, hash y chunker: implementados.
- Embeddings Gemini de 3.072 dimensiones: adaptador implementado; pendiente primera prueba real con credencial.
- Proyecto Supabase independiente `Radar Empleos 2.0`: creado en `us-east-1`; esquema aplicado y verificado.
- Persistencia de versiones del CV, fragmentos, ofertas y evaluaciones: primera versión implementada.
- Seguridad RLS: habilitada en las seis tablas.
- Recuperación semántica pgvector: función SQL y adaptador Python implementados.
- Interfaz Streamlit: registro/inicio de sesión, ingesta de CV local y evaluación manual de ofertas implementados.
- Pendiente: prueba integrada real con cuenta Auth, API Gemini y CV local; historial visual de evaluaciones; benchmark de 50 ofertas; migración completa de ingesta y fuentes automáticas.

## Inicio local

Siga los pasos de [Puesta en marcha local](docs/SETUP_LOCAL.md). En resumen:

1. Crear y activar entorno virtual.
2. Instalar `requirements.txt`.
3. Copiar `.env.example` a `.env` y completar las claves del proyecto nuevo.
4. Configurar `CV_PDF_PATH` con la ruta local del CV.
5. Ejecutar `streamlit run app.py`.

## Supabase

El proyecto independiente se identifica en `supabase/README.md`. El esquema reproducible está en `supabase/schema.sql`. No aplicar en la base productiva.

## Seguridad

- Este repositorio debe permanecer privado.
- No versionar CV, postulaciones, cachés, archivos `.env`, service-role keys ni sesiones.
- La app opera con sesión autenticada y políticas RLS; nunca exponer una clave privilegiada en el cliente.
- El PDF original permanece local; solo se transmite el texto extraído a Gemini para embeddings y evaluación.

## Principio de evaluación

Los embeddings ayudan a recuperar fragmentos relevantes; **no determinan por sí solos la compatibilidad ni el veredicto**. La evaluación combina evidencia recuperada, restricciones explícitas y Gemini. El benchmark humano será la referencia para medir calidad.
