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


## 2026-11-24 — Elevación temporal de topes internos para medir cuota Gemini (CHG-2026-008)

- Se confirma que 250 fragmentos y 15 evaluaciones por 24 horas eran topes internos de Radar, no límites publicados por Google.
- Se elevan temporalmente a 1.000 fragmentos y 100 evaluaciones por ventana móvil de 24 horas para medir el comportamiento real de Gemini con el proyecto configurado.
- Se mantienen lotes de 90 embeddings, espera de 60 segundos entre lotes y reintentos ante errores transitorios.
- Un error 429/RESOURCE_EXHAUSTED se conserva como señal de límite real; no se reintenta indefinidamente.
- Los topes siguen siendo configurables mediante RADAR_MAX_DAILY_JOB_CHUNKS y RADAR_MAX_DAILY_EVALUATIONS en entorno/Streamlit Secrets.
- Esta modificación no aumenta cuotas de Google, no habilita facturación, no modifica Supabase y no altera datos ni credenciales.
- El aumento no garantiza que se procesen 1.000 fragmentos: la cuota efectiva del modelo y el presupuesto de facturación del proyecto siguen aplicando.
