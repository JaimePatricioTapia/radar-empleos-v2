# Bitácora de implementación

## 2026-11-19 — Inicialización

- Se creó el repositorio privado independiente `radar-empleos-v2`.
- Se agregó estructura inicial de configuración, lectura del CV, chunking determinístico, adaptador de embeddings, esquema de evaluación, evaluador Gemini y métricas básicas.
- Se agregaron pruebas unitarias iniciales para chunking y métricas.
- No se copiaron PDF, cachés, secretos, sesiones de navegador ni datos de postulaciones.
- Se creó el proyecto Supabase independiente `Radar Empleos 2.0` en `us-east-1` (project ref: `lgnlrrvkcugexzvfxhug`), sin modificar el proyecto anterior.
- Se aplicó el esquema inicial: seis tablas, RLS, pgvector (3072 dimensiones), función de recuperación semántica del CV e índices HNSW.
- Se agregaron índices para las claves foráneas señaladas por el asesor de rendimiento.
- Verificación SQL: 6 tablas, 8 índices críticos y 1 función de recuperación presentes; las seis tablas tienen RLS habilitado.
- Asesor de seguridad: sin hallazgos. Los avisos de índices no utilizados son esperables en una base nueva y vacía.
- No se han cargado todavía datos del CV ni ofertas laborales.
- No se migró todavía el dashboard ni los módulos de ingesta.

## Próximos pasos

1. Ejecutar las pruebas en un entorno Python y corregir cualquier incompatibilidad.
2. Validar chunking sobre una copia local del CV (sin subirla al repositorio).
3. Generar embeddings y verificar dimensiones/versionado.
4. Completar pruebas de integración con un usuario Auth de prueba y datos sintéticos.
5. Validar la ingesta del CV local y búsqueda semántica con Gemini.
6. Migrar la lógica de evaluación y conectar benchmark humano.
7. Auditar y portar ingesta y Streamlit.
