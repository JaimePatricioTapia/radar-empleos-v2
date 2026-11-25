# Supabase de Radar 2.0

## Entorno requerido

Crear un proyecto Supabase NUEVO para Radar 2.0. No usar el proyecto productivo del Radar anterior.

El proyecto de desarrollo creado para esta implementación es:
- Nombre: `Radar Empleos 2.0`
- Project ref: `lgnlrrvkcugexzvfxhug`
- Región: `us-east-1` (misma región del proyecto Radar de Empleo existente)
- Organización: `JaimePatricio's Org`

El proyecto se creó con cotización de US$ 0 mensuales. Los consumos adicionales dependen del uso y del plan.

## Aplicar el esquema

1. Abrir el SQL Editor del proyecto nuevo.
2. Revisar que el nombre/ID del proyecto corresponda a Radar 2.0.
3. Ejecutar `schema.sql`.
4. Verificar que exista la extensión `vector` en el esquema `extensions`.
5. Confirmar que las tablas tienen RLS habilitado.
6. En Database > Settings / Data API, revisar la exposición del esquema `public`. Los proyectos nuevos no exponen automáticamente tablas a la Data API; habilitar solo lo necesario.
7. Crear un usuario Auth de prueba y validar que una sesión autenticada solo lea/escriba sus propias filas.

El esquema fue aplicado al proyecto independiente Radar Empleos 2.0 y verificado. Este archivo conserva el bootstrap SQL revisable para reproducir el esquema en otro entorno. No ejecutar en producción.

## Modelo de datos

- `cv_versions`: hash y metadatos de cada versión del CV.
- `cv_chunks`: texto segmentado y embedding por fragmento.
- `job_offers`: texto y metadatos de ofertas.
- `job_chunks`: fragmentos/embeddings de ofertas.
- `evaluations`: veredicto, score, salida JSON, modelo, prompt y evidencia.
- `applications`: seguimiento del proceso de postulación.\n- `user_search_portals`: portales personalizados persistentes por usuario.\n- `user_search_terms`: cargos y funciones personalizados por usuario.

Los embeddings se generan con el mismo modelo y dimensión para consultas y documentos. El vector se almacena como `vector(3072)`; HNSW indexa una expresión `halfvec(3072)` para respetar el límite de dimensiones del índice.

## Acceso

La app debe usar una clave publicable/anon junto con una sesión Auth válida. Nunca colocar `service_role` ni una secret key en Streamlit público, navegador, GitHub o `.env.example`. RLS es una segunda barrera, no un sustituto de autenticación.


## Preferencias de búsqueda persistentes

El esquema incluye `user_search_portals` y `user_search_terms`. Ambas tablas tienen RLS y políticas por `auth.uid()`; solo el rol `authenticated` recibe permisos de lectura/escritura. Los términos distinguen `cargo` de `funcion`. El archivo `schema.sql` incluye también estas tablas para reproducir el bootstrap.
