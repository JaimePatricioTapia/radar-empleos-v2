# Radar de Empleos 2.0

Nueva versión independiente del Radar de Empleos. Este repositorio no modifica ni despliega cambios en `radar-empleos-jptn`.

## Objetivos de la versión 2.0

1. Mantener una única fuente de verdad para el CV, con lectura dinámica, hash SHA-256 y versionamiento explícito.
2. Incorporar segmentación semántica (chunks) del CV y embeddings para recuperar evidencia pertinente a cada oferta.
3. Evaluar ofertas con Gemini mediante salida estructurada, evidencia trazable y reglas determinísticas para restricciones.
4. Construir un benchmark reproducible de ofertas etiquetadas por revisión humana.
5. Comparar versiones de prompts/modelos y detectar regresiones.
6. Mantener Supabase/Postgres como persistencia, incorporando pgvector solo cuando se ejecute la migración de desarrollo.
7. Reutilizar, tras auditoría, la ingesta y experiencia Streamlit del Radar original.

## Estado

**Fase 0 — Repositorio y arquitectura:** iniciada.

No se ha copiado el CV, datos personales, cachés de usuario, secretos ni sesiones de navegador desde el repositorio anterior.

## Estructura prevista

```text
radar-empleos-v2/
├── app.py
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   └── EVALUATION_PLAN.md
├── prompts/
│   └── evaluator_system.md
├── src/
│   ├── config.py
│   ├── cv/
│   │   ├── reader.py
│   │   ├── chunker.py
│   │   └── embeddings.py
│   └── evaluation/
│       ├── schemas.py
│       ├── evaluator.py
│       └── metrics.py
├── tests/
│   ├── fixtures/
│   └── test_cv_pipeline.py
└── data/
    └── evaluation/
        └── README.md
```

## Inicio local

1. Crear un entorno virtual: `python -m venv .venv`.
2. Activarlo y ejecutar `pip install -r requirements.txt`.
3. Copiar `.env.example` a `.env` y completar las credenciales.
4. Configurar `CV_PDF_PATH` con la ruta local del CV. El PDF debe permanecer fuera de Git.
5. Ejecutar pruebas: `pytest -q`.

Las funciones que requieren Gemini o Supabase deben poder probarse con dobles/mocks sin consumir API ni modificar datos reales.

## Seguridad y separación de entornos

- Este repositorio debe permanecer privado.
- No versionar CV, datos de postulaciones, cachés, archivos `.env`, service-role keys ni sesiones de navegador.
- La base Supabase de desarrollo debe ser distinta de la productiva.
- No ejecutar migraciones sobre producción.
- Las evaluaciones de benchmark no deben escribir ofertas en la tabla productiva.

## Principio de evaluación

Los embeddings ayudan a recuperar fragmentos relevantes; **no determinan por sí solos la compatibilidad ni el veredicto**. La evaluación final combina evidencia recuperada, reglas explícitas, perfil estructurado y Gemini. El benchmark humano será la referencia para medir calidad.
