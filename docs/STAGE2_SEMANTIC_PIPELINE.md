# Etapa 2 — Preselección semántica y evaluación económica

## Flujo

1. Las ofertas NUEVA con descripción suficiente se dividen en Job Chunks (máximo 1.100 caracteres, con solapamiento en párrafos largos).
2. Gemini Embeddings genera vectores de 3.072 dimensiones para esos fragmentos. El proceso trabaja por lotes de 100 ofertas y solo procesa ofertas que aún no tienen Job Chunks.
3. La función `rank_job_offers_by_cv` compara los vectores de los Job Chunks con los CV Chunks de la versión activa. El resultado es una similitud semántica de preselección, no afinidad laboral.
4. Se selecciona un máximo configurable (por defecto 35) de ofertas todavía no evaluadas con la versión activa del CV.
5. `retrieve_cv_evidence_for_offer` recupera los fragmentos del CV más cercanos a los vectores de la oferta ya almacenados. No genera nuevos embeddings de consulta.
6. Gemini recibe la descripción completa, el contexto de estrategia profesional y la evidencia recuperada. Devuelve score 0–100, veredicto, fortalezas, brechas y requisitos.
7. Se guardan las evaluaciones con modelo, versión de prompt y IDs de evidencia. La oferta recibe `affinity_score`, `sector_category` y `priority_score`.

## Diferencias entre métricas

- `semantic_score`: similitud vectorial para ordenar candidatos antes de llamar a Gemini.
- `affinity_score`: compatibilidad laboral evaluada por Gemini con evidencia del CV.
- `priority_score`: prioridad estratégica para ordenar el trabajo de postulación. Fórmula actual: 75% afinidad + 25% ponderación sectorial (Minería 100, Proveedor minero 92, Tecnología/Consultoría 62, Banca/Finanzas 52, Otros 30).

La prioridad no altera la afinidad. Los pesos son parámetros de producto que se podrán calibrar tras revisar los primeros resultados.

## Preferencias aplicadas como filtros

- No evaluar cargos Scrum Master.
- No priorizar Banco Santander.
- No evaluar empresas del sector salud; una mención incidental a beneficios de salud en la descripción no excluye una oferta.
- Prioridad estratégica para Minería y Proveedor minero.
- La evaluación puede reconocer la transferencia de experiencia operacional minera y experiencia tecnológica/funcional bancaria, pero no puede inventar experiencia o certificaciones.

## Operación incremental y ahorro de tokens

La app separa dos acciones deliberadamente:

1. **Preparar ofertas:** procesar lotes de 100 ofertas por ejecución. Se repite hasta que el contador "Pendientes de preparar" llegue a cero. Esta fase solo genera embeddings; no llama a Gemini.
2. **Evaluar las mejores:** recién cuando todas las ofertas aptas están vectorizadas, se ejecuta el ranking global y se envía a Gemini un top configurable (35 por defecto).

Así se evita evaluar las primeras ofertas capturadas antes de conocer la similitud de las restantes. La función de ranking excluye las ofertas ya evaluadas con el CV activo. Las descripciones insuficientes quedan pendientes de enriquecimiento y no consumen llamadas de Gemini. Los errores de evaluación se muestran para permitir reintento.

## Historial y no repetición

- `offer_lifecycle_events` registra cambios de estado.
- `job_offers.lifecycle_status` acepta NUEVA, POSTULADO, DESCARTADO, CADUCADO y ERROR.
- Los 59 registros POSTULADO y 220 DESCARTADA del Radar anterior fueron migrados; los 59 postulados también se reflejan en `applications`.
- Los puntajes antiguos quedan en `raw_metadata.legacy_*`; no se copian a `affinity_score`.
- La ingesta compara hash y URL exacta. El hash de Indeed conserva el parámetro `jk`, que identifica cada aviso y no debe eliminarse como si fuera tracking.

## Limitaciones actuales

- El clasificador sectorial inicial es heurístico; debe revisarse con muestras reales.
- El puntaje de Gemini debe calibrarse contra revisión humana.
- Los avisos sin descripción suficiente necesitan un paso posterior de enriquecimiento antes de poder evaluarse.
- La primera ejecución local real es necesaria para validar la integración Gemini + sesión autenticada de Supabase.
