# Etapa 1 — Descubrimiento multifuente

## Incluido

- LinkedIn, Indeed y Google Jobs mediante python-jobspy.
- Conectores HTTP/API públicos para Chiletrabajos, Computrabajo, Con tu Talento, BNE, Codelco, Finning y Get on Board.
- Normalización de título, empresa, ubicación, descripción, fecha, URL, fuente y metadatos.
- Deduplicación por URL canónica/hash dentro del lote y contra job_offers por usuario.
- Persistencia en job_offers con sesión autenticada y RLS.
- Dashboard para seleccionar fuentes, cargos y límite por consulta, ejecutar un barrido y ver resultados/enlaces.
- No invoca Gemini ni crea evaluaciones en esta etapa: la captura queda separada de la evaluación.

## Límites deliberados

- LinkedIn se consulta por JobSpy; no se usan credenciales personales ni sesión privada.
- Los portales pueden cambiar su HTML, API o políticas. Cada fuente falla de forma aislada y el resumen muestra errores por fuente.
- Con tu Talento y algunos listados pueden devolver extractos cortos; el enriquecimiento completo y la vectorización corresponden a la etapa siguiente.
- Laborum, Trabajando.com y Antofagasta Minerals quedan fuera de esta primera pasada: en producción dependían de Playwright/sesión persistente y sus selectores requieren prueba actual.
- No se garantiza exhaustividad absoluta: la cobertura depende de consultas, límite y disponibilidad de cada portal.

## Operación

1. Iniciar sesión en Radar 2.0.
2. Abrir Búsqueda automática de empleos.
3. Seleccionar fuentes y cargos, definir límite y ejecutar.
4. Revisar las ofertas capturadas y abrir el aviso original.

Las ofertas se guardan sin evaluación. La etapa siguiente generará embeddings en job_chunks, recuperará evidencia del CV con pgvector y evaluará con Gemini.
