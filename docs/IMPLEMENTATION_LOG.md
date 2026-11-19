# Bitácora de implementación

## 2026-11-19 — Inicialización

- Se creó el repositorio privado independiente `radar-empleos-v2`.
- Se agregó estructura inicial de configuración, lectura del CV, chunking determinístico, adaptador de embeddings, esquema de evaluación, evaluador Gemini y métricas básicas.
- Se agregaron pruebas unitarias iniciales para chunking y métricas.
- No se copiaron PDF, cachés, secretos, sesiones de navegador ni datos de postulaciones.
- No se conectó Supabase ni se ejecutaron migraciones.
- No se migró todavía el dashboard ni los módulos de ingesta.

## Próximos pasos

1. Ejecutar las pruebas en un entorno Python y corregir cualquier incompatibilidad.
2. Validar chunking sobre una copia local del CV (sin subirla al repositorio).
3. Generar embeddings y verificar dimensiones/versionado.
4. Definir esquema pgvector en una instancia Supabase de desarrollo.
5. Migrar la lógica de evaluación y conectar benchmark humano.
6. Auditar y portar ingesta y Streamlit.
