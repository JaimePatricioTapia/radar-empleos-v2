# Flujo de evaluación de ofertas

1. El usuario inicia sesión con Supabase Auth.
2. Procesa su PDF local. Se guarda el texto segmentado y embeddings; el PDF binario no se transmite.
3. Pega una oferta laboral con cargo y descripción.
4. Radar calcula un hash SHA-256 y guarda la oferta en `job_offers`.
5. Gemini genera un embedding de consulta con tarea `RETRIEVAL_QUERY`.
6. La RPC `match_cv_chunks` recupera evidencia del CV activo mediante pgvector, filtrada por versión y protegida por RLS.
7. Gemini evalúa oferta + metadatos del CV + fragmentos recuperados.
8. Se guarda el resultado estructurado, modelo, versión del prompt y referencias de evidencia en `evaluations`.

La similitud vectorial solo recupera evidencia; no se convierte directamente en puntuación de compatibilidad. La recomendación final proviene del evaluador estructurado y debe contrastarse con el benchmark humano.
