# Radar de Empleos 2.0 — Requisitos funcionales y auditoría visual

- **Documento:** RF-RADAR-001
- **Versión:** 1.0 (línea base inicial)
- **Fecha:** 2026-11-21
- **Estado:** Borrador controlado para validación del propietario
- **Rama de trabajo:** `feature/requirements-visual-audit-classification`
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

## 3. Requisitos funcionales

| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-001 | Autenticación | Un usuario no autenticado no puede acceder a pantallas ni datos privados. | Crítica |
| RF-002 | Aislamiento de datos | Dos usuarios autenticados no pueden leer ni alterar los datos privados del otro. | Crítica |
| RF-003 | Gestión del CV | Cada usuario puede procesar su CV; el archivo original no se publica ni se expone a otros usuarios. | Crítica |
| RF-004 | Búsqueda multifuente | Permite seleccionar portales y cargos, ejecutar consultas, informar resultados, duplicados y errores. | Alta |
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
- Acceso público autenticado con datos privados por usuario: decisión de arquitectura acordada; requiere prueba de aislamiento multiusuario y protección del despliegue antes de abrir registros a terceros.

## 10. Registro incremental de cambios aprobados

| ID | Fecha | Requisitos | Decisión autorizada | Estado |
|---|---|---|---|---|
| CHG-2026-001 | 2026-11-21 | RF-007, RF-017, RF-018, VIS-003–VIS-005, QA-006–QA-007, QA-018–QA-020 | El propietario autorizó elevar el umbral de recomendación de 75% a 85% y consolidar búsqueda, preparación semántica y evaluación en una única acción con continuidad y recuperación. | Aprobado para implementación; pendiente de código y pruebas. |
| CHG-2026-002 | 2026-11-22 | RF-019–RF-022, VIS-011–VIS-012, QA-021–QA-024 | El propietario autorizó preparar Radar 2.0 para Streamlit Community Cloud, mantener GitHub privado, procesar CV mediante carga temporal y aislar clientes de Supabase por sesión. No autoriza hacer público el repositorio ni cambiar el esquema de Supabase. | Aprobado para implementación; pendiente de pruebas integradas y autorización GitHub/Streamlit. |

Las nuevas decisiones se agregan como filas; no se sobrescriben decisiones históricas. Toda modificación futura de este documento requiere presentar previamente la propuesta al propietario y esperar su autorización explícita.

## 11. Regla de aprobación

Una versión solo se considera lista para integrar cuando:
- las pruebas automatizadas pasan;
- las pruebas de aceptación críticas pasan;
- no hay regresiones funcionales conocidas;
- las capturas requeridas están adjuntas y revisadas;
- el repositorio y secretos siguen protegidos;
- el propietario aprueba el Pull Request.

