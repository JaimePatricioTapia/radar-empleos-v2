# Guía de prueba controlada — Radar de Empleos 2.0 MVP

## Propósito
Validar que Radar permite pasar de un CV a oportunidades concretas, con evidencia visible y sin descartar automáticamente avisos por renta desconocida o por puntajes todavía no calibrados.

## Antes de empezar
- Ingrese con su cuenta habitual de Radar 2.0.
- Compruebe que aparece el CV correcto como versión activa.
- No vuelva a procesar el mismo PDF si el hash y los embeddings ya están guardados.
- Confirme que la pantalla informa los límites operativos efectivos: hasta 250 fragmentos de ofertas y 15 evaluaciones por ventana móvil de 24 horas. Son límites internos preventivos, no cuotas oficiales de Google.

## Prueba 1 — Perfil del CV
1. Abra «Competencias detectadas con evidencia».
2. Revise las competencias, categorías, secciones y extractos.
3. Compruebe que SQL/Power BI u otra herramienta solo muestre nivel cuando el CV lo declara explícitamente.
4. Marque mentalmente o anote las competencias mal detectadas o ausentes para corregir la taxonomía.

**Aceptación:** cada competencia mostrada debe incluir un extracto de respaldo. No deben inventarse años de experiencia ni niveles.

## Prueba 2 — Búsqueda multifuente
1. Mantenga seleccionados los portales disponibles.
2. Use las familias y cargos que realmente representan su trayectoria: análisis funcional/negocio, proyectos TI, minería/operaciones, riesgo/seguridad, datos y producto digital.
3. Inicie «Buscar y evaluar ofertas automáticamente».
4. Observe el estado, el avance por etapa, los resultados por fuente y las incidencias.

**Aceptación:** un fallo de un portal no debe ocultar resultados de los demás. La pantalla debe diferenciar ofertas encontradas, nuevas, duplicadas, descartadas por pertinencia, preparadas y evaluadas.

## Prueba 3 — Detención y recuperación
1. Si necesita detener el proceso, use «Cancelar proceso completo».
2. Compruebe que termina la operación externa en curso y que no inicia nuevas etapas.
3. Compruebe que lo ya guardado permanece disponible.
4. Si una ejecución desaparece, verifique que el botón de búsqueda vuelve a habilitarse cuando el worker ya no está vivo.

**Aceptación:** cancelar no borra ofertas, fragmentos ni evaluaciones confirmadas. «Detener búsqueda y procesar resultados» debe seguir siendo distinto de cancelar todo.

## Prueba 4 — Bandeja y afinidad
1. Revise «Recomendadas» (85 o más).
2. Revise «Revisión manual» (70–84).
3. Abra «Otras evaluadas bajo 70».
4. Abra el análisis de una oferta y revise fortalezas, brechas, requisitos, evidencia, restricciones e incertidumbres.

**Aceptación:** ninguna oferta evaluada desaparece solo por quedar bajo 85. Las bandas 85 y 70 son provisionales y deben corregirse después de comparar contra decisiones humanas.

## Prueba 5 — Preferencia de renta
Verifique estas reglas en ofertas reales o con evaluación manual:
- Renta líquida desde $1.000.000: cumple la preferencia.
- Renta líquida inferior: reduce el indicador de atractivo, pero no la afinidad ni la elegibilidad.
- Renta no informada: permanece sin penalización.
- Renta bruta/imponible o monto sin base clara: no se convierte a líquido ni se penaliza.

**Aceptación:** el sistema nunca debe confundir afinidad profesional con conveniencia económica.

## Prueba 6 — Postulación
1. Abra la publicación original desde la ficha.
2. Confirme manualmente que el aviso sigue activo y que cumple los requisitos.
3. Postule en el portal del empleador.
4. Cambie el estado a «POSTULADO» en Radar y guarde una nota breve.

**Aceptación:** Radar registra seguimiento; no postula automáticamente ni afirma que una oferta sigue vigente sin comprobarla.

## Limitaciones conocidas del MVP
- La cobertura depende de los límites, disponibilidad y estructura de cada portal.
- Las fechas de publicación desconocidas se identifican; no se debe asumir que el aviso es reciente.
- Gemini puede pausar evaluaciones cuando se agota una cuota gratuita del proveedor; el trabajo guardado queda pendiente.
- El inventario de competencias es una primera taxonomía determinística y requiere revisión humana.
- Los puntajes y umbrales no están calibrados con un conjunto de vacantes etiquetadas por personas.
- El MVP no automatiza postulaciones ni inventa datos del CV.

## Registro de incidencias para la prueba
Al reportar un problema, conserve: etapa del proceso, mensaje exacto, portal, cargo consultado, hora aproximada y si la oferta quedó guardada. No comparta claves, tokens, cookies ni secretos.
