# Arquitectura propuesta — Radar 2.0

## Flujo de CV

1. Leer el PDF local configurado en `CV_PDF_PATH`.
2. Calcular SHA-256 sobre los bytes del archivo.
3. Comparar el hash con la versión previamente procesada.
4. Si cambió, extraer texto, segmentar y regenerar embeddings; si no cambió, reutilizar los artefactos válidos.
5. Registrar por separado hash del CV, versión del chunker y modelo de embeddings. Un cambio de modelo o estrategia de segmentación también invalida los vectores correspondientes.

## Flujo de evaluación

1. Normalizar oferta y extraer requisitos.
2. Aplicar filtros determinísticos para restricciones explícitas.
3. Recuperar chunks pertinentes mediante embeddings (y, cuando sea útil, búsqueda textual).
4. Entregar a Gemini la oferta, perfil estructurado y evidencia recuperada.
5. Validar la salida Pydantic y coherencia básica entre requisitos y veredicto.
6. Persistir evaluación, prompt version, modelo, hash CV, hash oferta y evidencia utilizada.

## Diseño de pruebas

- Pruebas unitarias sin red para lectura, hash, chunking, esquemas y métricas.
- Benchmark con ofertas etiquetadas por una persona, incluyendo casos negativos y ambiguos.
- Pruebas de consistencia con paráfrasis de una misma oferta.
- Pruebas de no invención y cumplimiento de restricciones.
- Comparación de versiones con el mismo dataset y configuración.

## Decisiones pendientes de validar

- Confirmar estructura de datos actual de Supabase y diseñar migración aislada para desarrollo.
- Elegir estrategia de embeddings y dimensiones efectivas del modelo seleccionado.
- Determinar tamaño/solapamiento de chunks tras inspeccionar el CV real; no asumir que el primer chunker es definitivo.
- Auditar y migrar ingesta y Streamlit desde el repositorio original sin credenciales ni datos personales.
