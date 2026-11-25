# Radar de Empleos 2.0 — Requisitos funcionales y auditoría visual

- **Documento:** RF-RADAR-001
- **Versión:** 1.2 (línea base + control de cuota gratuita + preferencias persistentes de búsqueda)
- **Fecha:** 2026-11-25
- **Estado:** Borrador controlado para validación del propietario
- **Rama de trabajo:** `feature/free-tier-token-optimization`
- **Principio:** una mejora no puede eliminar ni degradar funciones existentes sin aprobación expresa.

## 1. Propósito y control de cambios

Este documento es la referencia funcional y visual para desarrollar, probar y publicar Radar 2.0. Cada cambio debe indicar qué requisito modifica, qué pruebas ejecuta y si altera alguna pantalla o flujo existente.

Toda modificación debe:
1. vincularse a un requisito o incidencia;
2. incluir pruebas automatizadas cuando sea viable;
3. incluir evidencia visual de las pantallas afectadas;
4. comprobar regresiones de funciones no relacionadas;
5. permanecer en una rama y Pull Request separados hasta su validación;
6. no fusionarse a la rama estable hasta la aprobación del propietario.

## 2. Arquitectura y privacidad acordadas

### 2.1 Acceso a la aplicación
- La aplicación podrá estar publicada en un dominio propio y ser accesible desde Internet.
- El acceso a funciones y datos requerirá autenticación.
- La interfaz podrá compartirse con otros usuarios autenticados.
- Que la aplicación sea accesible no significa que el código fuente sea público.

### 2.2 Código y despliegue
- El repositorio GitHub debe permanecer **privado**.
- Los usuarios finales no tendrán permisos de escritura en el repositorio ni en el entorno de despliegue.
- El despliegue se realizará desde una rama protegida o desde una versión aprobada; no desde cambios realizados por usuarios en ejecución.
- Las claves privilegiadas, secretos, variables de entorno y credenciales nunca se incluirán en el repositorio ni en el navegador.
- Los cambios de código se realizarán mediante ramas y Pull Requests revisables.

### 2.3 Privacidad de información
- El CV original y sus contenidos son privados por usuario.
- Los fragmentos, embeddings, evaluaciones y datos derivados del CV deben estar aislados por usuario.
- Las políticas RLS de Supabase deben impedir que un usuario consulte o modifique CV, evaluaciones, postulaciones o registros privados de otro usuario.
- La publicación de la aplicación no autoriza a compartir los CV ni los resultados personales.
- Antes de habilitar cuentas de terceros se debe probar el aislamiento entre dos usuarios distintos.
- La aplicación no debe depender de una clave service-role en el cliente.

### 2.4 Passkeys / biometría
- La autenticación biométrica se implementará en una rama independiente.
- Se utilizará WebAuthn/Passkeys; Touch ID será una modalidad del autenticador del dispositivo, no una huella enviada al servidor.
- Se mantendrá un método alternativo de acceso y recuperación.
- El identificador RP y los orígenes permitidos se definirán para el dominio final antes del registro definitivo de Passkeys.
- La implementación debe probar registro, inicio de sesión, cancelación, credencial no disponible, cierre de sesión y recuperación.

### 2.5 Restricción económica y cuota gratuita
- El presupuesto disponible para servicios externos de pago es **CLP $0**. La aplicación debe funcionar solo con planes gratuitos.
- La optimización de tokens, solicitudes y cuotas API es un requisito no funcional crítico, no una mejora opcional.
- Antes de llamar a Gemini se deben aplicar filtros locales y deduplicación; los resultados ya calculados se reutilizan.
- Los embeddings y evaluaciones se deben persistir incrementalmente para no repetir trabajo tras un error.
- Los errores 429/5xx transitorios deben respetar el tiempo de reintento indicado por el proveedor y aplicar backoff limitado.
- El proceso debe detenerse de forma controlada al alcanzar un presupuesto preventivo interno, conservar los resultados y mostrar qué queda pendiente.
- Los límites internos deben ser configurables y conservadores; nunca deben interpretarse como la cuota exacta garantizada por Google.
- Queda prohibido introducir dependencias de planes pagados, activar facturación o cambiar a un proveedor de pago para resolver límites.

## 3. Requisitos funcionales

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | Autenticación | Un usuario no autenticado no puede acceder a pantallas ni datos privados. | Crítica |
| RF-002 | Aislamiento de datos | Dos usuarios autenticados no pueden leer ni alterar los datos privados del otro. | Crítica |
| RF-003 | Gestión del CV | Cada usuario puede procesar su CV; el archivo original no se publica ni se expone a otros usuarios. | Crítica |
| RF-004 | Búsqueda multifuente | Permite seleccionar portales, cargos y funciones; conserva preferencias personalizadas por usuario y reporta resultados, duplicados y errores. | Alta |
| RF-005 | Preparación semántica | Permite preparar ofertas por lotes sin ejecutar la evaluación generativa de Gemini. | Alta |
| RF-006 | Evaluación de afinidad | Evalúa ofertas con evidencia recuperada del CV y conserva trazabilidad del resultado. | Alta |
| RF-007 | Umbral de recomendación | Solo se muestran como recomendadas las ofertas con afinidad >= 85%, calculada contrastando requisitos de la oferta con evidencia verificable del CV. | Alta |
| RF-008 | Orden de recomendaciones | Se ordenan por afinidad descendente; el sector solo desempata. | Alta |
| RF-009 | Filtro minero | Permite alternar entre todos los sectores y solo minería/proveedores mineros. | Alta |
| RF-010 | Clasificación rápida | Cada oferta permite cambiar su estado mediante acciones visibles: Postulado, Descartado, Caducado y Error. | Crítica |
| RF-011 | Motivo/nota | El usuario puede añadir una nota opcional al clasificar una oferta. | Media |
| RF-012 | Persistencia de estado | El cambio de estado se persiste y genera el evento de ciclo de vida correspondiente. | Crítica |
| RF-013 | Historial | Las ofertas clasificadas dejan de mezclarse con las pendientes, pero siguen disponibles en una vista de historial/filtrado. | Alta |
| RF-014 | Evaluación manual | Se puede pegar una oferta externa y solicitar evaluación sin ejecutar una búsqueda. | Media |
| RF-015 | Passkeys | Un usuario puede registrar y usar una Passkey, manteniendo alternativa de acceso. | Alta |
| RF-016 | Auditoría | Cada versión registra requisitos afectados, pruebas, evidencias visuales y resultado de regresión. | Alta |
| RF-017 | Ejecución integral con una acción | Un único botón inicia búsqueda multifuente, preparación semántica, evaluación de afinidad y actualización de la bandeja priorizada, sin exigir acciones manuales intermedias. | Crítica |
| RF-018 | Continuidad y recuperación del proceso | El flujo integral procesa por lotes hasta agotar ofertas elegibles, conserva resultados parciales, evita duplicados y permite reanudar desde la etapa pendiente si ocurre un error. | Alta |
| RF-025 | Operación exclusivamente gratuita | El Radar no requiere servicios pagados; aplica filtros locales, caché, deduplicación, límites preventivos y detención segura para proteger cuotas gratuitas. | Crítica |
| RF-026 | Persistencia incremental de embeddings | Cada sublote de embeddings exitoso se persiste inmediatamente y los reintentos calculan solo los fragmentos faltantes. | Crítica |
| RF-027 | Recuperación de errores de proveedor | Los errores transitorios 429/5xx respetan retryDelay y backoff; los errores permanentes no se reintentan indefinidamente. | Alta |
| RF-028 | Estado y progreso observable en tiempo real | Durante la ejecución integral se muestra una barra de progreso basada en eventos reales, etapa actual, portal, cargo/consulta, consultas completadas y pendientes, ofertas encontradas/nuevas/duplicadas, errores, tiempo transcurrido y hora de última actualización. El estado se actualiza al terminar cada consulta/lote y no debe aparentar avance cuando una operación está bloqueada. | Crítica |
| RF-029 | Detención controlada y procesamiento parcial | Durante la búsqueda, el usuario puede solicitar «Detener y procesar resultados». La aplicación deja de iniciar nuevas consultas después de finalizar o agotar el tiempo de espera de la consulta en curso, persiste el avance, cierra ordenadamente el descubrimiento y continúa automáticamente con preparación semántica y evaluación de todas las ofertas recopiladas. No descarta ni revierte ofertas, embeddings o evaluaciones ya persistidos; lo que quede pendiente debe poder reanudarse. | Crítica |
| RF-030 | Antigüedad máxima de publicaciones | La búsqueda aplica una ventana de 14 días: descarta ofertas con fecha de publicación verificable anterior al límite; cuando el portal no expone fecha, el aviso se marca explícitamente como fecha no verificada y se contabiliza por separado, sin afirmar que cumple la ventana. | Crítica |
| RF-031 | Ofertas nuevas visibles durante descubrimiento | Cada oferta nueva confirmada en Supabase se refleja en el panel de ejecución sin esperar a que terminen todas las consultas. | Alta |
| RF-032 | Ejecución no bloqueante y eventos reales | El proceso se ejecuta fuera del hilo de renderizado de Streamlit; la interfaz consulta eventos de progreso y mantiene disponibles los controles de detención. El progreso refleja consultas/etapas realmente completadas, no tiempo estimado. | Crítica |

## 4. Requisitos de clasificación de ofertas

### 4.1 Acciones visibles
La bandeja de ofertas pendientes debe presentar acciones directas y claramente identificables:
- **Postulado**
- **Descartado**
- **Caducado**
- **Error**

La acción **Postulado** debe actualizar también el registro correspondiente en `applications`, evitando duplicados mediante la clave de conflicto definida por el esquema.

La acción **Descartado** debe permitir registrar un motivo opcional. Las acciones deben solicitar confirmación cuando la operación pueda resultar ambigua o difícil de revertir.

### 4.2 Estados y vistas
- La bandeja principal debe mostrar ofertas pendientes de decisión.
- Las ofertas clasificadas no deben desaparecer de la base ni perder su historial.
- Debe existir una vista o filtro para consultar ofertas Postuladas, Descartadas, Caducadas y con Error.
- El filtro sectorial no debe cambiar ni borrar el estado de una oferta.
- Una oferta con afinidad inferior al 85% no debe aparecer como recomendación; su registro histórico se conserva según las reglas de trazabilidad.

### 4.3 Criterio de no regresión
Cambiar el selector de estado por botones, o viceversa, no se considera equivalente sin validación del propietario. La clasificación rápida es una función explícita y debe mantenerse visible.

## 5. Inventario de pantallas y línea base visual

La siguiente lista es el inventario funcional que debe tener evidencia visual. Las capturas iniciales reales deben tomarse de la aplicación ejecutándose localmente; no se deben sustituir por maquetas ni capturas inventadas.

| ID visual | Pantalla/estado | Evidencia requerida |
|---|---|---|
| VIS-001 | Acceso | Inicio de sesión y creación de cuenta. |
| VIS-002 | Mi currículum | Ruta/selección de CV, estado procesado y resultado. No mostrar contenido sensible en capturas compartidas. |
| VIS-003 | Búsqueda integral | Portales, cargos, límite y un único botón que inicia el flujo completo; progreso por etapas y resultados finales. |
| VIS-004 | Preparación semántica | Progreso y métricas de preparación integrados al flujo automático; no requiere botón independiente. |
| VIS-005 | Evaluación de afinidad | Progreso, métricas, errores y resultados de evaluación integrados al flujo automático; no requiere botón independiente. |
| VIS-006 | Bandeja priorizada | Tarjeta completa de oferta, afinidad, prioridad, URL y acciones de clasificación. |
| VIS-007 | Filtro de minería | Estado visual con todos los sectores y solo minería. |
| VIS-008 | Historial | Ofertas clasificadas por estado y sus notas. |
| VIS-009 | Evaluación manual | Formulario y resultado de evaluación. |
| VIS-010 | Passkeys | Registro, acceso con Passkey y alternativa de acceso. |
| VIS-011 | Ejecución cloud | Aplicación iniciada desde la URL Streamlit, pantalla de acceso y estado de servicio sin revelar secretos. |
| VIS-012 | Carga cloud del CV | Selector de archivo PDF, confirmación de procesamiento y resultado; no mostrar contenido sensible ni ruta del servidor. |
| VIS-013 | Progreso y control de ejecución | Barra de progreso y panel de estado con etapa, portal/cargo/consulta actual, contadores de consultas y ofertas, errores, última actualización y acción «Detener y procesar resultados» mientras la búsqueda esté activa. Debe distinguir ejecución activa, espera/reintento, detención solicitada, procesamiento parcial, completado y error recuperable. |
| VIS-014 | Ofertas descubiertas en vivo | Lista de últimas ofertas recién persistidas, con portal y estado de verificación de fecha, actualizada durante el descubrimiento. |

### 5.1 Capturas de referencia
Guardar capturas aprobadas en `docs/visual-baseline/` con nombres estables:
`VIS-001-login.png`, `VIS-003-search.png`, `VIS-006-inbox.png`, etc.

Las capturas deben:
- usar una resolución de navegador constante (recomendado 1440 × 1000);
- ocultar datos personales, correos, CV, tokens y cualquier secreto;
- registrar fecha, commit y navegador;
- distinguir estados vacíos, con resultados, error y carga cuando correspondan;
- actualizarse solo cuando el propietario apruebe el cambio visual.

**Estado de esta versión:** inventario definido; capturas reales pendientes de recopilar y aprobar. No se declara una línea base visual aprobada hasta que existan esas capturas.

## 6. Pruebas de aceptación y regresión

| ID prueba | Escenario | Resultado esperado |
|---|---|---|
| QA-001 | Abrir la aplicación sin sesión | Solo se muestra acceso/registro. |
| QA-002 | Usuario A intenta consultar datos del usuario B | Acceso denegado por RLS. |
| QA-003 | Ejecutar búsqueda multifuente | Se informan encontradas, nuevas, duplicadas y errores. |
| QA-004 | Preparar siguiente lote | Se generan chunks/embeddings; no se llama al evaluador Gemini. |
| QA-005 | Evaluar ofertas | Se evalúa el lote configurado y se registra trazabilidad. |
| QA-006 | Afinidad 84% | No aparece en recomendaciones. |
| QA-007 | Afinidad 85% | Sí puede aparecer en recomendaciones si existe evidencia suficiente y no aplica una exclusión. |
| QA-008 | Ordenar recomendaciones | Afinidad descendente; sector no adelanta menor afinidad. |
| QA-009 | Filtro solo minería | Solo MINERIA y PROVEEDOR_MINERO. |
| QA-010 | Clasificar como Postulado | Estado persistido y aplicación asociada creada/actualizada. |
| QA-011 | Clasificar como Descartado | Estado persistido, nota opcional e historial disponible. |
| QA-012 | Clasificar como Caducado o Error | Estado persistido e historial disponible. |
| QA-013 | Consultar historial | Los estados clasificados siguen consultables. |
| QA-014 | Registrar e iniciar con Passkey | WebAuthn completa el flujo y crea sesión válida. |
| QA-015 | Cancelar Passkey o no disponer de ella | No se bloquea el acceso alternativo. |
| QA-016 | Revisión visual | Las pantallas no afectadas conservan estructura y controles de referencia. |
| QA-017 | Repositorio/despliegue | Repositorio privado; usuario final no puede modificar código ni secretos. |
| QA-018 | Ejecución integral | Una sola acción ejecuta búsqueda, preparación, evaluación y refresco de la bandeja sin botones intermedios. | Crítica |
| QA-019 | Reanudación y no duplicación | Ante un fallo, los resultados ya guardados se conservan; al reintentar no se duplican ofertas ni se pierde el progreso y se continúa con las pendientes. | Alta |
| QA-020 | Evaluación requisito-CV | La puntuación distingue requisitos obligatorios/deseables, evidencia directa/transferible y brechas; no atribuye al CV competencias no demostradas. | Crítica |
| QA-021 | Secretos de despliegue | La app inicia con secretos de Streamlit; ninguna clave aparece en Git, HTML, mensajes de error ni logs de interfaz. | Crítica |
| QA-022 | Sesiones concurrentes A/B | Dos usuarios autenticados en sesiones distintas no comparten tokens, identidad ni datos; RLS limita cada consulta a auth.uid(). | Crítica |
| QA-023 | Ingesta de CV cloud | Un PDF válido se procesa y activa solo para el usuario autenticado; un PDF inválido falla de forma controlada y los temporales se eliminan. | Crítica |
| QA-024 | Smoke test Community Cloud | La rama y entrypoint seleccionados instalan dependencias, arrancan la app y permiten autenticación, carga CV y consulta inicial de bandeja. | Alta |
| QA-025 | Error Gemini 429 con retryDelay | Se espera el tiempo indicado por Google, se reintenta de forma limitada y no se repite una llamada antes del plazo. | Crítica |
| QA-026 | Fallo entre sublotes de embeddings | Los sublotes ya guardados permanecen; al reanudar se calculan únicamente los índices faltantes. | Crítica |
| QA-027 | Presupuesto de embeddings | Al alcanzar 250 fragmentos en una ventana móvil de 24 horas, el Radar detiene nuevas solicitudes y conserva pendientes. | Crítica |
| QA-028 | Presupuesto de evaluaciones | Al alcanzar 15 evaluaciones en una ventana móvil de 24 horas, el Radar detiene llamadas generativas adicionales. | Crítica |
| QA-029 | Servicios exclusivamente gratuitos | La configuración y el flujo no requieren activar facturación ni usar modelos/servicios de pago. | Crítica |
| QA-030 | Progreso real de búsqueda | Al completar consultas se actualizan etapa, portal, cargo, contadores y última actividad; los errores y reintentos se identifican. La barra no aumenta por tiempo transcurrido ni muestra porcentajes inventados. | Crítica |
| QA-031 | Detener y procesar resultados parciales | Al solicitar la detención durante descubrimiento, no se inician nuevas consultas tras cerrar la actual; las ofertas ya encontradas permanecen persistidas y se ejecutan preparación y evaluación automáticamente sobre el conjunto recopilado. | Crítica |
| QA-032 | Recuperación después de detener | Si falla la preparación/evaluación posterior o se interrumpe la sesión, se conservan resultados y lotes completados; al reanudar se procesan solo pendientes, sin duplicar ofertas ni repetir embeddings/evaluaciones ya guardados. | Crítica |
| QA-033 | Ventana de 14 días | Una oferta con fecha de 15 días se descarta; una de 14 días o menos puede continuar; una fecha desconocida se contabiliza y etiqueta sin presentarla como verificada. | Crítica |
| QA-034 | Progreso en segundo plano | La búsqueda continúa mientras la interfaz muestra eventos y permite solicitar detención; ningún callback de trabajo llama directamente a Streamlit desde el hilo de fondo. | Crítica |
| QA-035 | Oferta incremental | Tras persistir una oferta nueva, aparece en el feed de ejecución antes de que finalice el resto del descubrimiento. | Alta |
| QA-036 | Contenido de oferta malicioso | Instrucciones incrustadas en la descripción de un aviso no alteran el prompt, las reglas ni el resultado del evaluador; el texto externo se trata como dato no confiable. | Crítica |

## 7. Procedimiento de auditoría visual por versión

Para cada Pull Request:

1. Identificar las pantallas afectadas y los requisitos vinculados.
2. Ejecutar pruebas automatizadas: `pytest -q`.
3. Iniciar la aplicación y recorrer los casos QA relevantes.
4. Capturar las pantallas con la misma resolución y datos de prueba controlados.
5. Comparar las capturas con la línea base aprobada.
6. Revisar manualmente diferencias de contenido dinámico, orden, controles, espaciado y estados.
7. Adjuntar capturas antes/después al Pull Request.
8. Registrar pruebas aprobadas, fallidas y pendientes.
9. No fusionar si desaparece un control existente o falla una prueba crítica, salvo aprobación expresa.

Cuando sea viable, automatizar capturas con Playwright y comparación de imágenes. La comparación pixel a pixel debe complementarse con revisión funcional: textos dinámicos, fechas, resultados y datos variables pueden producir diferencias legítimas.

## 8. Registro de decisiones y cambios

Mantener un registro por cambio con esta estructura:

| Campo | Descripción |
|---|---|
| ID de cambio | Identificador único (CHG-AAAA-NNN). |
| Pull Request / commit | Enlace y SHA. |
| Requisitos afectados | IDs RF y VIS. |
| Motivo | Problema que se resuelve. |
| Archivos afectados | Lista de archivos. |
| Pruebas | IDs QA y resultado. |
| Evidencia visual | Capturas antes/después. |
| Riesgo | Bajo/medio/alto y justificación. |
| Aprobación | Pendiente/aprobado/rechazado. |

## 9. Estado de implementación al crear esta línea base

- Búsqueda multifuente, preparación semántica y evaluación por lotes: presentes en la rama de afinidad.
- Umbral de afinidad >=85%, orden por afinidad y filtro minero: cambio aprobado el 2026-11-21; implementación y validación pendientes.
- Clasificación de ofertas: existe actualmente un selector de estado con botón «Guardar estado» en cada tarjeta. El usuario reporta que echa de menos la botonera de clasificación rápida; la restauración de acciones directas y la vista de historial quedan como trabajo pendiente.
- Passkeys: trabajo separado en rama propia; no se considera implementado.
- Capturas visuales aprobadas: pendientes de levantar desde la aplicación real.
- Control de cuota gratuita: implementado y fusionado en feature/streamlit-cloud-deployment (PR #10, commit b6ee22f8a69d792d3ab863c036048d25121bc0d4). GitHub Actions: 51 pruebas aprobadas. Valores predeterminados de 250 fragmentos de ofertas y 15 evaluaciones por ventana móvil de 24 horas, configurables mediante RADAR_MAX_DAILY_JOB_CHUNKS y RADAR_MAX_DAILY_EVALUATIONS; son topes preventivos internos, no cuotas oficiales de Google. Pendiente smoke test real en Streamlit Community Cloud.
- Acceso público autenticado con datos privados por usuario: decisión de arquitectura acordada; requiere prueba de aislamiento multiusuario y protección del despliegue antes de abrir registros a terceros.

## 10. Registro incremental de cambios aprobados

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-001 | 2026-11-21 | RF-007, RF-017, RF-018, VIS-003–VIS-005, QA-006–QA-007, QA-018–QA-020 | El propietario autorizó elevar el umbral de recomendación de 75% a 85% y consolidar búsqueda, preparación semántica y evaluación en una única acción con continuidad y recuperación. | Aprobado para implementación; pendiente de código y pruebas. |
| CHG-2026-002 | 2026-11-22 | RF-019–RF-022, VIS-011–VIS-012, QA-021–QA-024 | El propietario autorizó preparar Radar 2.0 para Streamlit Community Cloud, mantener GitHub privado, procesar CV mediante carga temporal y aislar clientes de Supabase por sesión. No autoriza hacer público el repositorio ni cambiar el esquema de Supabase. | Aprobado para implementación; pendiente de pruebas integradas y autorización GitHub/Streamlit. |
| CHG-2026-003 | 2026-11-23 | RF-025–RF-027, QA-025–QA-029 | El propietario ordenó priorizar operación exclusivamente gratuita y optimización estricta de cuota. Se autorizó auditoría comparativa con Radar original, filtros locales, presupuestos preventivos, reintentos con retryDelay y persistencia incremental/reanudable de embeddings. No se autorizan servicios pagados ni cambios de esquema Supabase. | Implementado y fusionado mediante PR #10; 51 pruebas aprobadas. Pendiente smoke test en la URL pública de Streamlit. |
| CHG-2026-004 | 2026-11-23 | RF-028–RF-029, VIS-013, QA-030–QA-032 | El propietario solicita visibilidad verificable del avance durante la búsqueda y una acción segura para detener el descubrimiento y procesar automáticamente las ofertas recopiladas, preservando persistencia incremental y reanudación. | Implementado y fusionado mediante PR #14; CI aprobada. Smoke test en Streamlit Cloud pendiente. |
| CHG-2026-005 | 2026-11-23 | RF-030–RF-032, VIS-014, QA-033–QA-036 | El propietario autoriza incorporar una ventana de 14 días, feed incremental de ofertas, ejecución en segundo plano, parada cooperativa y frontera de confianza para contenido externo. Se conserva el umbral 85%, la operación gratuita y la arquitectura Supabase existente. | Implementado y fusionado mediante PR #14 (commit 44f0e509); CI de PR y rama de despliegue aprobadas. Smoke test de Streamlit Cloud pendiente. |

Las nuevas decisiones se agregan como filas; no se sobrescriben decisiones históricas. Toda modificación futura de este documento requiere presentar previamente la propuesta al propietario y esperar su autorización explícita.

## 11. Regla de aprobación

Una versión solo se considera lista para integrar cuando:
- las pruebas automatizadas pasan;
- las pruebas de aceptación críticas pasan;
- no hay regresiones funcionales conocidas;
- las capturas requeridas están adjuntas y revisadas;
- el repositorio y secretos siguen protegidos;
- el propietario aprueba el Pull Request.



## 12. Notas de implementación de la mejora de búsqueda reciente

- JobSpy recibe el filtro nativo `hours_old=336` para LinkedIn e Indeed, además del control de antigüedad aplicado por el orquestador.
- El orquestador normaliza fechas ISO, fechas de calendario y expresiones relativas en español/inglés; descarta publicaciones verificablemente más antiguas de 14 días.
- Las fuentes que no informan una fecha fiable no se etiquetan falsamente como recientes: se conservan con `publication_date_status=unknown` y se contabilizan por separado para no perder oportunidades potencialmente vigentes.
- Las ofertas nuevas se emiten al feed después de confirmarse su persistencia.
- Un portal que acumula dos errores consecutivos omite las consultas restantes de esa fuente y permite que los otros portales continúen; el panel informa las consultas omitidas.
- La búsqueda y el procesamiento se ejecutan en un hilo de trabajo; el hilo de interfaz recibe eventos y puede solicitar detener el descubrimiento tras la consulta actual. La preparación y evaluación continúan con el conjunto persistido.
- El evaluador recibe una instrucción explícita para tratar publicaciones y fragmentos del CV como datos no confiables y no obedecer instrucciones incrustadas.
- Los cambios se fusionaron en `feature/streamlit-cloud-deployment` mediante PR #14, commit `44f0e509613d52297a945828eacc23ac6625310a`.
- GitHub Actions aprobó compilación y pruebas automatizadas tanto en el PR como en la rama de despliegue. La validación visual/funcional desde Streamlit Community Cloud sigue pendiente porque el entorno de ejecución alojado no pudo inspeccionarse desde esta sesión.


## 13. Metodología de identificación de cargos desde el CV (CHG-2026-006)

### 13.1 Decisión de arquitectura

El campo «Cargo objetivo» deja de ser el único generador de consultas. El Radar debe construir un perfil ocupacional a partir de la versión activa del CV y derivar familias funcionales de búsqueda. Los cargos que el usuario haya indicado se conservan como señales de prioridad, pero no son una barrera para descubrir oportunidades con otros títulos.

La primera implementación será determinística y auditable, sin añadir consumo de Gemini ni embeddings adicionales: utiliza el texto de los fragmentos del CV ya almacenados para reconocer evidencia de funciones, herramientas, sectores y responsabilidades. No debe inferir certificaciones, niveles de dominio, resultados cuantificados ni experiencia que no esté respaldada por el CV. Una evolución con extracción generativa requerirá presupuesto y aprobación separados.

### 13.2 Perfil ocupacional derivado

El perfil se compone de:
- funciones y responsabilidades demostrables;
- competencias y herramientas explícitas;
- sectores/industrias con experiencia acreditada;
- familias funcionales de cargos y sus sinónimos locales;
- nivel de prioridad y evidencia del CV que justifica cada familia;
- preferencias y exclusiones del usuario (ubicación, modalidad, sectores/cargos excluidos, salario cuando esté configurado).

Cada familia tendrá: identificador, nombre funcional, prioridad, títulos equivalentes, términos de competencias/dominio, evidencia que la activó y consultas emitidas. El resultado será reproducible para un mismo CV y versión de reglas.

### 13.3 Familias iniciales a evaluar

La configuración inicial debe considerar, sin asumir que todas son automáticamente elegibles:
1. Análisis de negocio y procesos: Business Analyst, Analista de Negocios, Analista de Procesos, Analista Funcional.
2. Proyectos y transformación TI: Jefe/Coordinador de Proyectos TI, Project Manager TI, PMO, Transformación Digital.
3. Tecnología minera y sistemas operacionales: Analista TI Minería, Sistemas Mineros, Tecnología/Transformación Operacional.
4. Riesgo tecnológico y seguridad TI: Analista de Riesgo Tecnológico, Seguridad TI, Ciberseguridad (solo si las funciones del CV lo respaldan).
5. Datos y analítica: Analista de Datos, BI y analítica (ponderando las herramientas y el nivel real declarado).
6. Producto digital: Product Owner, Analista de Producto, Product Manager (sin atribuir experiencia no demostrada).

Los cargos Scrum Master y roles de salud/Banco Santander no deben ser propuestos como objetivos prioritarios por las exclusiones vigentes. La ingeniería minera y la experiencia operacional deben permanecer como ventaja diferenciadora y no quedar ocultas por la trayectoria TI.

### 13.4 Generación y ejecución de consultas

- Generar términos en español e inglés cuando sean pertinentes al mercado chileno.
- Buscar por función y sinónimos, no solo por coincidencia literal del título.
- Combinar títulos con competencias y dominio cuando el portal admita consultas compuestas.
- Aplicar prioridad y límite de consultas por portal para proteger la cuota gratuita y evitar ráfagas.
- LinkedIn conserva una consulta booleana agrupada por ejecución; otros portales reciben consultas individuales controladas.
- Guardar en metadatos de la oferta la familia y consulta de origen, sin cambiar el esquema de Supabase.
- Mostrar al usuario las familias priorizadas, los títulos consultados y el origen de cada oferta.
- Las preferencias explícitas siguen filtrando oportunidades; los cargos objetivo previos actúan como pistas de búsqueda, no como lista cerrada.

### 13.5 Evaluación y ranking

La identificación de familia solo amplía el descubrimiento. No equivale a afinidad. Cada aviso debe seguir evaluándose contra la descripción completa y evidencia recuperada del CV, con brechas obligatorias/deseables y competencias directas/transferibles diferenciadas. El umbral de recomendación continúa en 85%; similitud de palabras, embeddings o pertenencia a una familia no pueden por sí solos generar una recomendación. Los resultados bajo el umbral se conservan con trazabilidad.

### 13.6 Requisitos nuevos

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-033 | Perfil ocupacional derivado del CV | El Radar analiza la versión activa del CV y produce funciones, competencias, herramientas, sectores y evidencia; no solicita volver a cargar el CV ni usa Gemini/embeddings adicionales para esta extracción inicial. | Crítica |
| RF-034 | Familias funcionales de cargos | Se generan familias priorizadas con títulos equivalentes, sinónimos ES/EN, términos de dominio y evidencia de CV; las familias sin evidencia suficiente se excluyen o se etiquetan como exploratorias. | Crítica |
| RF-035 | Cargo objetivo no excluyente | Los cargos configurados por el usuario se conservan como señales de prioridad, pero la búsqueda también incluye familias sustentadas por el CV. | Crítica |
| RF-036 | Consultas trazables por familia | Cada consulta registra familia, términos y prioridad; las ofertas nuevas conservan la procedencia en metadatos existentes, sin migración de base de datos. | Alta |
| RF-037 | Preferencias y exclusiones | Ubicación, modalidad, sectores/cargos excluidos y demás restricciones explícitas se aplican como filtros; no se recomienda una oportunidad incompatible solo por alta afinidad técnica. | Crítica |
| RF-038 | Control de expansión de consultas | El generador limita consultas por familia y portal, conserva LinkedIn agrupado, respeta cuotas gratuitas y comunica consultas planeadas/ejecutadas/omitidas. | Crítica |

### 13.7 Visualización y pruebas

Añadir VIS-015: «Perfil ocupacional y familias de búsqueda», con evidencia de las familias priorizadas, títulos equivalentes, términos, prioridad y fundamento resumido del CV. La vista no debe exponer el CV completo ni fragmentos sensibles.

| ID prueba | Escenario | Resultado esperado |
|---|---|---|
| QA-037 | CV con experiencia BA, banca digital y minería | Se identifican familias BA/procesos, proyectos TI y minería/operaciones cuando exista evidencia textual. |
| QA-038 | CV sin experiencia explícita en ciberseguridad avanzada | No se presenta como competencia acreditada ni se inventa seniority; como máximo se clasifica como exploratoria si existe evidencia adyacente. |
| QA-039 | Cargos objetivo vacíos o demasiado estrechos | Se generan consultas desde las familias sustentadas por el CV. |
| QA-040 | Cargos objetivo personalizados | Se conservan como señales adicionales sin eliminar familias derivadas. |
| QA-041 | Exclusión de Scrum Master, salud y empleadores excluidos | No se generan objetivos prioritarios ni se recomiendan ofertas que infrinjan exclusiones. |
| QA-042 | Misma versión de CV y reglas | El perfil y las consultas son reproducibles, sin llamadas generativas adicionales. |
| QA-043 | Oferta descubierta por alias de una familia | Se conserva family_id/family_name/query_origin en raw_metadata y se muestra la procedencia. |
| QA-044 | Oferta con título coincidente pero requisitos no acreditados | La familia no fuerza la afinidad; la evaluación completa decide y el umbral >=85% se mantiene. |
| QA-045 | Expansión de familias en múltiples portales | Se aplican topes, LinkedIn agrupado, deduplicación y reporte de consultas planeadas/completadas/omitidas. |

### 13.8 Registro de cambio

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-006 | 2026-11-23 | RF-033–RF-038, VIS-015, QA-037–QA-045 | El propietario autoriza incorporar al Radar la metodología de ai-job-search: perfil desde CV, familias funcionales priorizadas, alias/términos de búsqueda, descubrimiento por competencias y dominio, trazabilidad de consultas y evaluación final contra el CV completo. Se mantienen 85%, 14 días, operación gratuita, progreso/detención segura y esquema Supabase existente. | En implementación en rama feature/cv-derived-role-families; pendiente CI, revisión y smoke test cloud. |



## 14. Autenticación del worker y diagnóstico de cero evaluaciones (CHG-2026-007)

### Hallazgo de ejecución real — 2026-11-23

La sesión de prueba descubrió ofertas y las persistió, pero la etapa 3 mostró 0 evaluadas, 0 preseleccionadas y 0 incidencias. La inspección de solo lectura de Supabase confirmó 1.053 ofertas nuevas históricas, 413 con descripciones utilizables, 250 fragmentos de ofertas y 0 evaluaciones. Los 250 fragmentos se crearon dentro de las últimas 24 horas, alcanzando el presupuesto preventivo configurado. Una prueba SQL controlada con el contexto JWT del usuario devolvió candidatos en `rank_job_offers_by_cv`, lo que demuestra que existen ofertas semánticamente rankeables cuando `auth.uid()` está disponible. El worker anterior reutilizaba el mismo cliente Supabase del hilo Streamlit; el contexto Auth del RPC no estaba garantizado en el hilo secundario.

### Decisión correctiva

El worker debe crear un cliente Supabase independiente en el hilo principal, capturar la sesión del usuario autenticado y establecerla explícitamente con `auth.set_session(access_token, refresh_token)`. Se conserva la clave pública/anon configurada; nunca se usa service_role. Si no existe sesión válida, el proceso debe fallar temprano con un mensaje claro, no continuar con consultas RPC que devuelvan listas vacías.

### Requisitos nuevos

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-039 | Propagación segura de sesión al worker | El cliente de segundo plano es independiente y conserva el JWT del usuario mediante set_session; RLS y auth.uid() se mantienen activos; no se utiliza service_role ni se registran tokens. | Crítica |
| RF-040 | Cero candidatos nunca silencioso | Si el ranking devuelve 0 y existen job_chunks, se reporta diagnóstico de posible contexto Auth/RPC; si no hay chunks, se informa falta de preparación o presupuesto. No presentar 0 evaluaciones como éxito silencioso. | Crítica |
| RF-041 | Visibilidad del presupuesto durante evaluación | La etapa 3 muestra fragmentos usados/permitidos en 24 h, presupuesto restante y ofertas pendientes de preparación. Si se agotó el tope, se informa que se evaluarán los avisos previamente preparados y que los nuevos quedan pendientes. | Crítica |

### Pruebas nuevas

| ID | Escenario | Resultado esperado |
|---|---|---|
| QA-046 | Worker inicia desde una sesión autenticada | Crea cliente independiente, llama set_session con los tokens de esa sesión y ejecuta el pipeline con dicho cliente. |
| QA-047 | Sesión ausente o inválida | Falla temprano con mensaje accionable; no ejecuta el pipeline con identidad nula. |
| QA-048 | RPC semántico devuelve cero y hay job_chunks | Se registra incidencia explícita sobre contexto Auth/RPC. |
| QA-049 | RPC devuelve cero y no hay job_chunks | Se informa que no existen fragmentos preparados y se distingue el presupuesto agotado. |
| QA-050 | Presupuesto de embeddings agotado pero hay chunks previos | La interfaz muestra consumo, saldo cero y pendientes; continúa evaluación de chunks existentes. |

### Registro de cambio

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-007 | 2026-11-23 | RF-039–RF-041, QA-046–QA-050 | Corregir el contexto Auth del cliente Supabase en el worker, evitar ranking vacío silencioso y transparentar presupuesto/pendientes durante la etapa de evaluación. Mantener RLS, clave pública, topes y esquema existente. | Implementado en rama fix/background-supabase-auth-evaluation; pendiente CI y despliegue. |



## 15. Topes operativos para medición de cuota Gemini (CHG-2026-008)

### Decisión

Los límites originales de 250 fragmentos y 15 evaluaciones por ventana móvil de 24 horas eran barreras internas preventivas de Radar, no cuotas oficiales de Google. Se elevan temporalmente a 1.000 fragmentos y 100 evaluaciones para medir la capacidad efectiva del proyecto Gemini antes de volver a fijar límites operativos.

### Requisitos nuevos

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-042 | Distinguir topes Radar de cuotas Google | La interfaz identifica los topes como valores operativos de prueba y aclara que no son cuotas oficiales de Google. | Alta |
| RF-043 | Medir cuota efectiva de Gemini | Radar permite hasta 1.000 fragmentos y 100 evaluaciones por ventana móvil de 24 horas, manteniendo lotes, pausas y reintentos; los errores 429/RESOURCE_EXHAUSTED se registran y detienen ordenadamente la etapa afectada. | Alta |
| RF-044 | Mantener configuración explícita | Los topes pueden ajustarse mediante RADAR_MAX_DAILY_JOB_CHUNKS y RADAR_MAX_DAILY_EVALUATIONS; no se modifica facturación ni cuota del proyecto. | Alta |

### Pruebas nuevas

| ID prueba | Escenario | Resultado esperado |
|---|---|---|
| QA-051 | Cargar configuración por defecto | Se obtienen 1.000 fragmentos y 100 evaluaciones por 24 horas. |
| QA-052 | Gemini responde 429/RESOURCE_EXHAUSTED | Se conserva lo persistido, se detiene ordenadamente y se informa el límite efectivo observado. |
| QA-053 | Operador configura topes por entorno/Secrets | La configuración explícita prevalece sobre los valores por defecto. |

### Registro de cambio

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-008 | 2026-11-24 | RF-042–RF-044, QA-051–QA-053 | Elevar temporalmente los topes internos para medir la cuota efectiva de Gemini; mantener persistencia incremental, lotes de 90 y pausa de 60 segundos. Sin cambios en Supabase, facturación, credenciales o cuotas Google. | En revisión y CI. |


## 16. Pausa recuperable por retryDelay extenso de Gemini y tolerancia a fallas de portales (CHG-2026-009)

### Hallazgo de ejecución real — 2026-11-24

La aplicación desplegada informó: «Gemini evaluación transitoria (ClientError); reintento 1/4 en 22239.0 s». El evaluador utilizaba el retryDelay informado por Google directamente en time.sleep dentro del worker, lo que podía mantener la ejecución bloqueada aproximadamente 6 h 10 min. En la misma búsqueda, BNE respondió timeout de 12 s, Codelco respondió HTTP 403 y Finning HTTP 429.

### Decisión correctiva

- Si Gemini solicita esperar más de 60 segundos, Radar pausa la etapa de evaluación de inmediato y devuelve el control; no realiza una espera prolongada dentro del worker.
- Las evaluaciones ya confirmadas se mantienen. Las ofertas no evaluadas siguen pendientes y pueden recuperarse en una ejecución posterior sin recalcular evaluaciones existentes.
- Los reintentos breves de hasta 60 segundos se mantienen acotados.
- Los errores HTTP por portal permanecen aislados: 403/429 no se evaden ni se martillan con reintentos; se informa la incidencia y se permite continuar con otras fuentes. El circuito de fuente ya omite consultas posteriores tras errores consecutivos.

### Requisitos nuevos

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-045 | No bloquear por retryDelay largo | Si Gemini indica espera >60 s, no se ejecuta sleep prolongado; la etapa se pausa y comunica segundos indicados. | Crítica |
| RF-046 | Recuperación de evaluación pendiente | La pausa no elimina ofertas ni evaluaciones ya guardadas; las pendientes se vuelven a considerar en una ejecución posterior sin duplicar evaluaciones. | Crítica |
| RF-047 | Continuidad multifuente ante errores HTTP | Timeout, 403 y 429 de una fuente se registran por portal; no impiden consultar las fuentes restantes ni activan evasión de controles. | Alta |

### Pruebas nuevas

| ID prueba | Escenario | Resultado esperado |
|---|---|---|
| QA-054 | Gemini responde 429 con retryDelay de 22.239 s | Radar no duerme 6 h; devuelve pausa por cuota y conserva trabajo pendiente. |
| QA-055 | Gemini responde con retryDelay de 0,5 s | Se conserva el reintento breve y acotado. |
| QA-056 | El evaluador pausa por cuota dentro del lote | La etapa 3 termina en estado pausado, no como ejecución exitosa ni como error fatal. |
| QA-057 | BNE timeout, Codelco 403 o Finning 429 | Se registra la fuente fallida y las demás fuentes continúan. |

### Registro de cambio

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-009 | 2026-11-24 | RF-045–RF-047, QA-054–QA-057 | El propietario solicita corregir el bloqueo por retryDelay extenso y preservar la continuidad de búsqueda multifuente, manteniendo operación gratuita, persistencia y seguridad existentes. | Implementado en rama fix/gemini-long-retry-and-source-errors-2.1.3; pendiente CI y revisión. |


---

## 17. Preferencias persistentes de búsqueda por usuario (CHG-2026-010)

### 17.1 Objetivo

Evitar que el usuario tenga que volver a ingresar portales personalizados, cargos y funciones al iniciar una nueva sesión. Las preferencias deben guardarse en Supabase Radar 2.0 y quedar aisladas por cuenta. Esta mejora no modifica Radar 1 ni reutiliza sus tablas.

### 17.2 Modelo de datos

Se agregan exclusivamente dos tablas nuevas en el esquema `public`:

**`user_search_portals`**
- `id`: UUID, clave primaria.
- `user_id`: UUID obligatorio, FK a `auth.users(id)`, borrado en cascada.
- `name`: nombre visible del portal, entre 1 y 80 caracteres.
- `url_template`: URL HTTP(S) pública, máximo 1.000 caracteres. Puede contener `{query}`; si no lo contiene, el conector añade el parámetro de búsqueda `q=`.
- `enabled`: permite activar/desactivar el portal sin eliminarlo.
- `created_at`, `updated_at`: marcas de tiempo.

La URL se valida en la aplicación antes de consultarse. El conector debe seguir bloqueando redirecciones y destinos privados/no públicos; guardar una URL no implica que el sitio sea compatible con extracción HTML genérica.

**`user_search_terms`**
- `id`: UUID, clave primaria.
- `user_id`: UUID obligatorio, FK a `auth.users(id)`, borrado en cascada.
- `term_type`: solo `cargo` o `funcion`.
- `term`: texto de 2 a 160 caracteres.
- `normalized_term`: columna generada para normalizar mayúsculas y espacios.
- `enabled`: permite conservar y desactivar términos.
- `created_at`, `updated_at`: marcas de tiempo.
- Restricción única por usuario, tipo y término normalizado.

### 17.3 Reglas funcionales

| ID | Regla |
|---|---|
| RF-048 | Los portales personalizados se guardan en Supabase y se recuperan al iniciar sesión; no dependen de `st.session_state`. |
| RF-049 | El usuario puede crear, activar, desactivar y eliminar portales propios. Solo los habilitados se incluyen por defecto en la selección de búsqueda. |
| RF-050 | Los cargos personalizados se guardan por usuario y se presentan separados de las funciones. Los cargos sugeridos y derivados del CV siguen disponibles. |
| RF-051 | Las funciones/responsabilidades se gestionan como términos independientes de los cargos y pueden buscar avisos aunque su título no coincida literalmente. |
| RF-052 | La búsqueda combina cargos y funciones seleccionados. En LinkedIn se agrupan en una consulta booleana; en las demás fuentes se consulta cada término por separado. |
| RF-053 | Los términos personalizados seleccionados se guardan al iniciar la búsqueda y se recuperan en sesiones posteriores. El usuario puede eliminarlos. |
| RF-054 | Las preferencias son privadas por cuenta. Un usuario no puede leer, crear, actualizar ni eliminar las preferencias de otro usuario. |
| RF-055 | Los portales y términos predeterminados siguen disponibles aunque falle la carga de preferencias guardadas; el error se informa y no bloquea el acceso a la aplicación. |

### 17.4 Interfaz

- Expansor «Administrar portales personalizados»: formulario para nombre y URL; listado persistente; acciones Activar/Desactivar y Eliminar.
- Selector «Cargos objetivo»: incluye cargos predeterminados, cargos detectados en el CV y cargos propios guardados; permite escribir nuevos.
- Selector «Funciones y responsabilidades»: lista independiente con funciones sugeridas y personalizadas; permite escribir nuevas.
- Expansor «Administrar cargos y funciones guardados»: permite revisar y eliminar términos personalizados.
- Las funciones sugeridas no quedan todas seleccionadas automáticamente para evitar multiplicar consultas y consumir cuota; el usuario elige cuáles incorporar.
- Los portales personalizados habilitados se incorporan a la búsqueda y pueden desmarcarse en el selector general de fuentes.

### 17.5 Seguridad y privacidad

- RLS habilitado en ambas tablas.
- Políticas SELECT, INSERT, UPDATE y DELETE restringidas a `TO authenticated` y `(select auth.uid()) = user_id`.
- UPDATE exige tanto `USING` como `WITH CHECK`.
- Permisos de tabla concedidos solo a `authenticated`; no se concede acceso a `anon`.
- No se almacena información del CV ni credenciales de portales en estas tablas.
- La aplicación usa la sesión autenticada de Supabase; no introduce ni expone `service_role`.

### 17.6 Pruebas de aceptación

| ID prueba | Escenario | Resultado esperado |
|---|---|---|
| QA-058 | Guardar portal y cerrar/reabrir sesión | El portal sigue disponible para el mismo usuario. |
| QA-059 | Desactivar un portal guardado | Permanece almacenado, pero no se incluye por defecto en la búsqueda. |
| QA-060 | Guardar cargo y función personalizados | Ambos reaparecen en sus selectores respectivos al volver a iniciar sesión. |
| QA-061 | Buscar solo por funciones | Se ejecutan consultas por las funciones seleccionadas sin exigir un cargo. |
| QA-062 | Usuario A intenta leer/modificar preferencias de B | RLS impide el acceso. |
| QA-063 | Duplicar un término con mayúsculas distintas | No se crea un término duplicado para el mismo usuario y tipo. |
| QA-064 | Fallo al cargar preferencias | La aplicación informa el problema y conserva los selectores predeterminados. |
| QA-065 | Seleccionar cargos y funciones en LinkedIn | Se envía una única consulta agrupada; no se crea una consulta por cada término. |

### 17.7 Registro de cambio

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-010 | 2026-11-25 | RF-048–RF-055, QA-058–QA-065 | El propietario autoriza crear tablas nuevas y políticas RLS en Supabase Radar 2.0 para persistir portales, cargos y funciones; Radar 1 y tablas existentes quedan fuera de alcance. | Esquema aplicado y verificado; integración de interfaz/código en rama de trabajo, pendiente CI y despliegue. |
