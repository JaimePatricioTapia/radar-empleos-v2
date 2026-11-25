# Bitácora de implementación

## 2026-11-19 — Inicialización

- Se creó el repositorio privado independiente `radar-empleos-v2`.
- Se agregó estructura inicial de configuración, lectura del CV, chunking determinístico, adaptador de embeddings, esquema de evaluación, evaluador Gemini y métricas básicas.
- Se agregaron pruebas unitarias iniciales para chunking y métricas.
- No se copiaron PDF, cachés, secretos, sesiones de navegador ni datos de postulaciones.
- Se creó el proyecto Supabase independiente `Radar Empleos 2.0` en `us-east-1` (project ref: `lgnlrrvkcugexzvfxhug`), sin modificar el proyecto anterior.
- Se aplicó el esquema inicial: seis tablas, RLS, pgvector (3072 dimensiones), función de recuperación semántica del CV e índices HNSW.
- Se agregaron índices para las claves foráneas señaladas por el asesor de rendimiento.
- Verificación SQL: 6 tablas, 8 índices críticos y 1 función de recuperación presentes; las seis tablas tienen RLS habilitado.
- Asesor de seguridad: sin hallazgos. Los avisos de índices no utilizados son esperables en una base nueva y vacía.
- No se han cargado todavía datos del CV ni ofertas laborales.
- No se migró todavía el dashboard ni los módulos de ingesta.

## Próximos pasos

1. Ejecutar las pruebas en un entorno Python y corregir cualquier incompatibilidad.
2. Validar chunking sobre una copia local del CV (sin subirla al repositorio).
3. Generar embeddings y verificar dimensiones/versionado.
4. Completar pruebas de integración con un usuario Auth de prueba y datos sintéticos.
5. Validar la ingesta del CV local y búsqueda semántica con Gemini.
6. Migrar la lógica de evaluación y conectar benchmark humano.
7. Auditar y portar ingesta y Streamlit.


## 2026-11-24 — Elevación temporal de topes internos para medir cuota Gemini (CHG-2026-008)

- Se confirma que 250 fragmentos y 15 evaluaciones por 24 horas eran topes internos de Radar, no límites publicados por Google.
- Se elevan temporalmente a 1.000 fragmentos y 100 evaluaciones por ventana móvil de 24 horas para medir el comportamiento real de Gemini con el proyecto configurado.
- Se mantienen lotes de 90 embeddings, espera de 60 segundos entre lotes y reintentos ante errores transitorios.
- Un error 429/RESOURCE_EXHAUSTED se conserva como señal de límite real; no se reintenta indefinidamente.
- Los topes siguen siendo configurables mediante RADAR_MAX_DAILY_JOB_CHUNKS y RADAR_MAX_DAILY_EVALUATIONS en entorno/Streamlit Secrets.
- Esta modificación no aumenta cuotas de Google, no habilita facturación, no modifica Supabase y no altera datos ni credenciales.
- El aumento no garantiza que se procesen 1.000 fragmentos: la cuota efectiva del modelo y el presupuesto de facturación del proyecto siguen aplicando.


## 2026-11-24 — Pausa no bloqueante ante retryDelay extenso de Gemini (CHG-2026-009)

- El registro real de Streamlit mostró un reintento de evaluación programado a 22.239 segundos (aprox. 6 h 10 min), provocado por un 429/RESOURCE_EXHAUSTED de Gemini.
- Se identifica que el evaluador esperaba dentro del hilo de trabajo respetando literalmente retryDelay, bloqueando el cierre de la ejecución.
- Se incorpora una excepción de pausa explícita cuando el retryDelay supera 60 segundos. No se duerme durante horas ni se hacen reintentos automáticos durante una cuota probablemente agotada.
- La evaluación ya guardada permanece intacta; las ofertas aún no evaluadas permanecen pendientes para una nueva ejecución. El resultado informa pausa por cuota y segundos indicados por el proveedor.
- Los reintentos breves (hasta 60 s) conservan el comportamiento acotado existente.
- BNE timeout, Codelco HTTP 403 y Finning HTTP 429 son fallas aisladas por portal. No se evaden bloqueos; se mantiene la continuidad con otras fuentes y el cortacircuito por errores consecutivos.
- No se modifican Supabase, esquema/RLS, datos, credenciales, topes, facturación ni cuotas de Google.

## 2026-11-25 — Recuperación de cobertura de búsqueda (PR #22)

- Se eliminó la concatenación obligatoria de términos de dominio a cada cargo: ahora se consulta el título original para evitar filtros AND accidentales; los términos de dominio siguen como metadatos.
- Se restaura el límite inicial de 15 resultados por consulta, equivalente al de la primera versión.
- Indeed consulta Chile y Antofagasta y solicita descripciones; se deduplican los resultados entre ubicaciones.
- Se agrega Glassdoor mediante JobSpy como fuente independiente, con descarga de descripciones.
- LinkedIn conserva la descarga de descripciones desactivada y, ante bloqueos 403/429, no insiste con otra ubicación.
- Se mantienen los 14 días, la deduplicación, el filtro de pertinencia, la autenticación y el esquema actual de Supabase.
- Validación pendiente de CI y de una búsqueda real desde Streamlit; las fuentes externas pueden seguir limitando solicitudes.


## 2026-11-25 — Pausa inmediata por cuota diaria Gemini (PR siguiente)

- Se identifica explícitamente el error de cuota diaria Free Tier de generate_content y se interpreta el plazo de espera de Google (incluyendo formatos como 22h9m16s).
- En lugar de consumir cuatro reintentos adicionales por cada oferta, se pausa inmediatamente la evaluación y se conservan las ofertas y evaluaciones ya persistidas.
- Se agregan pruebas para parseo de espera, fallback de 24 horas y errores 503 no diarios.
- No se modifican cuotas, facturación, credenciales, Supabase ni datos.


## 2026-11-25 — Recuperación del estado de búsqueda y cancelación segura

- El filtro sectorial de la bandeja se aclara como filtro de visualización: no cambia los cargos ni inicia una búsqueda.
- Si el objeto de ejecución conserva un estado activo pero su hilo ya terminó, la interfaz recupera el estado y evita dejar deshabilitado el botón indefinidamente.
- Se agrega cancelación cooperativa del pipeline desde cualquier etapa; espera a que termine la llamada externa actual y luego detiene nuevas consultas/evaluaciones.
- La cancelación conserva en Supabase las ofertas, fragmentos y evaluaciones ya confirmados; no elimina ni modifica datos persistidos.
- Se mantiene la acción existente para detener solo el descubrimiento y procesar lo recopilado.
- No se modifican Supabase, RLS, secretos, credenciales ni facturación.


## 2026-11-25 — Perfil de competencias trazable para el MVP
- Se incorpora una taxonomía de competencias por familias funcionales, datos, riesgo/seguridad, producto, métodos y minería.
- Cada competencia detectada conserva sección, fragmento y extracto de respaldo del CV.
- Los niveles básico/intermedio/avanzado/experto solo se muestran cuando están expresamente declarados cerca de la competencia.
- El perfil se presenta en la interfaz y se entrega al evaluador junto con la evidencia recuperada.
- No se infieren años de experiencia ni se modifican tablas, RLS, secretos o datos históricos.
