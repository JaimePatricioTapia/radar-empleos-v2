# Arquitectura de Radar 2.0

## Flujo objetivo

1. Leer el PDF local y calcular SHA-256.
2. Comparar hash, versión del chunker y modelo de embeddings con el manifiesto persistido.
3. Si cambió algún componente, extraer texto y generar chunks.
4. Generar embeddings Gemini `gemini-embedding-001` de 3.072 dimensiones.
5. Persistir versión del CV, chunks y vectores en Supabase de desarrollo.
6. Ingerir ofertas conservando texto original, URL, fuente y hash.
7. Para evaluar una oferta, generar embedding de consulta, recuperar evidencia CV con pgvector y enviar solo evidencia pertinente a Gemini.
8. Guardar salida estructurada, versión del prompt/modelo y los IDs de evidencia.
9. Comparar predicciones con el benchmark humano.

## Persistencia

El modelo de datos está documentado en `docs/DATA_MODEL.md` y el SQL inicial en `supabase/schema.sql`. El PDF fuente no se almacena en Supabase ni GitHub. Se conservan el texto extraído, sus fragmentos, hashes y embeddings.

## Seguridad y entornos

- Supabase 2.0 debe ser un proyecto separado.
- Las tablas activan RLS y vinculan cada fila a `auth.uid()`.
- Las políticas no confían en metadatos editables por el usuario.
- La RPC de recuperación es `SECURITY INVOKER`, con filtro explícito de usuario y RLS como segunda barrera.
- La aplicación usa sesión Auth y clave publicable/anon; no usa service_role.
- El esquema SQL aún no se ha aplicado ni validado en una instancia.

## Embeddings

Se fija el modelo y dimensión en el manifiesto. Los embeddings de documentos usan tarea `RETRIEVAL_DOCUMENT`; las consultas, `RETRIEVAL_QUERY`. Ambos deben utilizar el mismo modelo y dimensión. La columna conserva `vector(3072)`; el índice HNSW usa una expresión `halfvec(3072)` porque pgvector limita HNSW a 4.000 dimensiones para halfvec y 2.000 para vector.

## Estado

La persistencia y recuperación tienen primeras implementaciones, pero la autenticación de la interfaz, la ingesta completa, las operaciones transaccionales y el benchmark continúan pendientes. No se debe tratar esta versión como despliegue productivo.
