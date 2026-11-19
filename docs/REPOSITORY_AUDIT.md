# Auditoría de origen y decisiones de migración

Origen auditado: `JaimePatricioTapia/radar-empleos-jptn`, rama `main`.

## Componentes existentes identificados

- `src/lector_cv.py`: localiza el PDF, extrae texto íntegro, calcula SHA-256 y mantiene una caché de estrategia indexada por el hash del CV.
- `src/evaluador_ia.py`: envía el CV y la oferta a Gemini y valida una respuesta Pydantic.
- `src/calibrador_aprendizaje.py`: resume postulaciones y descartes desde Supabase y produce directrices de calibración por prompting (in-context learning; no fine-tuning).
- `src/database.py`: persistencia y consultas de ofertas en Supabase.
- `app.py`: interfaz Streamlit y flujos de evaluación manual/automática.
- Módulos de ingesta: JobSpy, Playwright y portales específicos.

## Observaciones relevantes

- La evaluación manual lee el PDF y envía el texto completo al evaluador; no depende necesariamente de la caché de estrategia.
- La estrategia de búsqueda se reutiliza cuando el hash coincide. El hash debe seguir siendo la clave de invalidación del contenido; las fechas de metadatos no sustituyen esa comprobación.
- La evaluación actual usa el CV completo en el prompt. Radar 2.0 añadirá recuperación por fragmentos como una capa de evidencia, conservando un perfil estructurado y una vía de respaldo para evitar perder contexto.
- El aprendizaje actual ajusta directrices de prompt a partir de decisiones históricas. En 2.0 se mantendrá separado del benchmark para no contaminar las etiquetas de referencia.
- El repositorio de origen contiene archivos locales/personales que no deben copiarse a esta nueva base de código.

## Política de migración

Migrar por módulos, revisando cada archivo y sus dependencias. No copiar datos, CV, cachés, sesiones, secretos ni URLs de servicios productivos. Validar todo contra un entorno Supabase de desarrollo antes de conectar componentes.
