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
- Autenticación, carga de CV desde navegador con procesamiento temporal y evaluación manual: implementadas en la rama cloud; CI validado con 51 pruebas aprobadas. Pendiente únicamente el smoke test visual/funcional en la URL pública de Streamlit.
- Etapa 1 — búsqueda automática multifuente: implementada.
- Etapa 2 — fragmentación y embeddings de ofertas, preselección semántica pgvector, recuperación de evidencia CV sin embeddings extra, evaluación Gemini por lotes y ranking sectorial: implementada en la rama feature/semantic-evaluation-ranking; pendiente validación integrada local.
- Historial de estados: 59 postuladas + 220 descartadas migradas desde el Radar anterior; estados históricos auditables.

## Despliegue Streamlit Community Cloud

Consulte [docs/DEPLOY_STREAMLIT_CLOUD.md](docs/DEPLOY_STREAMLIT_CLOUD.md). El repositorio GitHub permanece privado; la aplicación Streamlit se publica con autenticación obligatoria y datos aislados por RLS, según autorización del propietario. Los secretos se configuran solo en la plataforma.

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
- Topes preventivos internos máximos de **250 fragmentos de ofertas** y **15 evaluaciones** por ventana móvil de 24 horas. Son límites conservadores del Radar, no una promesa de cuota oficial de Google. Los secretos pueden reducirlos, pero la aplicación no permite elevarlos por encima de esos máximos.
- Al alcanzar el tope, la búsqueda se pausa sin borrar resultados ni seguir consumiendo cuota; quedan pendientes para una ejecución posterior.

La evaluación del CV utiliza embeddings al procesarlo. No vuelva a cargar el mismo CV sin necesidad; primero verifique si ya está activo. La configuración de modelo y dimensiones debe mantenerse compatible con el esquema de Supabase (3072 dimensiones).

Los topes preventivos pueden ajustarse con variables de entorno o secretos de Streamlit:
- `RADAR_MAX_DAILY_JOB_CHUNKS=250`
- `RADAR_MAX_DAILY_EVALUATIONS=15`

Se recomienda mantener los valores predeterminados hasta comprobar el consumo real de la cuenta gratuita. Reducirlos disminuye el consumo; aumentarlos puede agotar más rápidamente la cuota del proveedor.


## Conectores de búsqueda

- `python-jobspy` está fijado a la versión `1.5.0` para evitar cambios silenciosos del extractor entre despliegues.
- LinkedIn se consulta una sola vez por ejecución, agrupando los cargos objetivo en una búsqueda booleana. No se solicita la descarga individual de cada descripción, porque esa opción multiplica las peticiones y puede provocar bloqueos HTTP 429.
- Indeed se consulta de forma independiente por cargo. Un fallo de LinkedIn no detiene Indeed ni los demás portales.
- Los errores reportados por JobSpy se incorporan al resumen de incidencias, en vez de presentarse como una búsqueda vacía sin explicación.
- Google Jobs no se ofrece como fuente seleccionable mientras JobSpy 1.5.0 lo reporte no disponible.


## Calidad de búsqueda — Radar 2.1.0

- Antes de persistir una oferta, un filtro determinístico comprueba señales de cargos objetivo y funciones de análisis, proyectos TI, producto, datos, riesgo y minería.
- Ocupaciones claramente ajenas (por ejemplo, conserjería, bodega, ventas presenciales o convivencia escolar) se descartan antes de consumir embeddings o evaluaciones Gemini, salvo que la descripción contenga varias señales técnicas/funcionales fuertes.
- Los casos dudosos se conservan cuando hay evidencia suficiente; el filtro no exige que el título coincida literalmente con el nombre del cargo.
- El resumen de ejecución informa cuántas ofertas se descartaron y muestra una muestra de títulos/motivos para auditar falsos positivos.
- Chiletrabajos deja de tratar cualquier etiqueta `article` como una tarjeta de empleo y restringe la extracción de descripciones a selectores propios de la descripción de la vacante.
- El filtro es local, gratuito y no modifica tablas, RLS, credenciales ni presupuestos de Supabase/Gemini.


## Radar 2.1.1 — Repetición de búsquedas

- Al terminar una ejecución, el resumen ofrece una acción explícita para iniciar otra búsqueda con los portales, cargos y máximo de resultados actualmente seleccionados.
- No permite solapar dos procesos de búsqueda.
- Si el presupuesto de embeddings está agotado, advierte que la nueva búsqueda puede descubrir y guardar ofertas, pero no preparará sus embeddings hasta la renovación del límite móvil de 24 horas.
- Las ofertas y fragmentos ya persistidos se conservan; no se borran al repetir la búsqueda.


## MVP — guía de primera prueba
Consulte [docs/MVP_TEST_GUIDE.md](docs/MVP_TEST_GUIDE.md). El MVP se considera apto para una prueba controlada cuando CI pasa y se valida manualmente el flujo autenticado de CV, búsqueda, evaluación, bandeja y estado de postulación. Los puntajes 85/70 son bandas provisionales, no calibradas con resultados de contratación.
