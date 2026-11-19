# Modelo de datos y persistencia

## Límites de responsabilidad

- El PDF original del CV permanece en el equipo local indicado por `CV_PDF_PATH`.
- Supabase conserva el texto extraído segmentado, hashes, metadatos y embeddings necesarios para recuperar evidencia.
- Las ofertas se conservan con su descripción original y hash para deduplicación.
- Las evaluaciones guardan la salida estructurada, modelo, versión de prompt y fragmentos usados.
- GitHub contiene código y documentación, nunca CV, ofertas privadas, sesiones ni credenciales.

## Decisiones técnicas

- Embeddings: `gemini-embedding-001`, 3.072 dimensiones.
- Almacenamiento: `extensions.vector(3072)`.
- Índice HNSW: expresión `embedding::extensions.halfvec(3072)`, métrica coseno.
- La búsqueda filtra por usuario autenticado y versión activa del CV.
- RLS se activa en todas las tablas y las políticas exigen `user_id = auth.uid()`.
- La función RPC es `SECURITY INVOKER`; no eleva privilegios.
- Los vectores de consulta y documentos deben provenir del mismo modelo y dimensión.

## Nota sobre el flujo actual

La persistencia de CV y ofertas está encapsulada en `src/db/repository.py`. La recuperación de evidencia está en `src/search/retriever.py`. La orquestación de ingesta, autenticación de usuario en Streamlit y transacciones atómicas se deben integrar en la siguiente iteración; no se debe considerar el pipeline completo listo para uso productivo todavía.
