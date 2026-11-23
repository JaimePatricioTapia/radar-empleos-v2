# Radar de Empleos 2.0

Nueva versión independiente del Radar de Empleos. Este repositorio no modifica ni despliega cambios en radar-empleos-jptn.

## Objetivos

1. Mantener una fuente de verdad del CV con hash SHA-256 y versionamiento.
2. Segmentar CV y ofertas en chunks y generar embeddings.
3. Recuperar evidencia pertinente mediante Gemini + pgvector.
4. Evaluar ofertas con Gemini, evidencia trazable y restricciones determinísticas.
5. Construir un benchmark reproducible de ofertas revisadas por una persona.
6. Mantener la base de datos de desarrollo separada de cualquier entorno productivo.

## Estado de implementación

- Lector de CV, hash y chunker: implementados.
- Embeddings Gemini de 3.072 dimensiones: adaptador implementado; requiere prueba integrada real.
- Proyecto Supabase independiente Radar Empleos 2.0: esquema aplicado y verificado.
- Persistencia de versiones del CV, fragmentos, ofertas y evaluaciones: implementada.
- Seguridad RLS: habilitada en las siete tablas.
- Recuperación semántica pgvector del CV: implementada.
- Autenticación, carga de CV desde navegador con procesamiento temporal y evaluación manual: implementadas en la rama cloud; pendientes de prueba integrada.
- Etapa 1 — búsqueda automática multifuente: implementada.
- Etapa 2 — fragmentación y embeddings de ofertas, preselección semántica pgvector, recuperación de evidencia CV sin embeddings extra, evaluación Gemini por lotes y ranking sectorial: implementada en la rama feature/semantic-evaluation-ranking; pendiente validación integrada local.
- Historial de estados: 59 postuladas + 220 descartadas migradas desde el Radar anterior; estados históricos auditables.

## Despliegue Streamlit Community Cloud

Consulte [docs/DEPLOY_STREAMLIT_CLOUD.md](docs/DEPLOY_STREAMLIT_CLOUD.md). El repositorio debe permanecer privado y los secretos se configuran en la plataforma.

## Inicio local

Siga docs/SETUP_LOCAL.md. En resumen: activar el entorno virtual, instalar requirements.txt, completar .env y ejecutar streamlit run app.py.

## Supabase

El esquema reproducible está en supabase/schema.sql. Aplicar SOLO en el proyecto de desarrollo Radar Empleos 2.0, nunca en la base productiva.

## Seguridad

- Mantener el repositorio privado.
- No versionar CV, postulaciones, cachés, archivos .env, service-role keys ni sesiones.
- La app usa sesión autenticada y políticas RLS; nunca exponer una clave privilegiada.
- El PDF original no se sube a GitHub ni se persiste en Supabase. En Streamlit Cloud se transmite para procesarlo en un archivo temporal del servidor, eliminado al finalizar; solo se persisten los datos derivados bajo RLS.

## Principio de evaluación

Los embeddings ayudan a recuperar fragmentos relevantes; no determinan por sí solos la compatibilidad ni el veredicto. La evaluación combina evidencia recuperada, restricciones explícitas y Gemini. El benchmark humano será la referencia para medir calidad.


## Operación con planes gratuitos (presupuesto $0)

El Radar debe funcionar exclusivamente con planes gratuitos. No se debe activar facturación ni incorporar proveedores de pago.

Protecciones incorporadas en la rama de optimización:
- Filtros locales y preselección por pertinencia antes de solicitar embeddings o evaluaciones generativas.
- Embeddings en lotes; cada sublote exitoso se guarda inmediatamente en Supabase.
- Reintentos limitados ante errores transitorios de Gemini, respetando el `retryDelay` del proveedor.
- Reanudación por índice de fragmento: los embeddings ya guardados no se vuelven a calcular.
- Topes preventivos internos de **250 fragmentos de ofertas** y **15 evaluaciones** por ventana móvil de 24 horas. Son límites conservadores del Radar, no una promesa de cuota oficial de Google.
- Al alcanzar el tope, la búsqueda se pausa sin borrar resultados ni seguir consumiendo cuota; quedan pendientes para una ejecución posterior.

La evaluación del CV utiliza embeddings al procesarlo. No vuelva a cargar el mismo CV sin necesidad; primero verifique si ya está activo. La configuración de modelo y dimensiones debe mantenerse compatible con el esquema de Supabase (3072 dimensiones).
