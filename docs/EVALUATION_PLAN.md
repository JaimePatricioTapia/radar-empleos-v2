# Plan de benchmark del evaluador

## Dataset inicial

Crear 50 ofertas anonimizadas y etiquetadas manualmente. Propuesta de distribución:

- 10 de compatibilidad muy alta.
- 10 de compatibilidad alta.
- 10 de compatibilidad parcial.
- 10 de compatibilidad baja.
- 10 con requisito excluyente, ambigüedad relevante o información insuficiente.

La etiqueta de referencia debe registrar score o rango esperado, veredicto, requisitos obligatorios, requisitos deseables, evidencia del CV, brechas y razón de decisión.

## Métricas

- Macro F1 para clasificación de veredictos.
- Matriz de confusión y precisión/recall por clase.
- Error absoluto medio del score, comparado contra el valor/rango humano.
- Tasa de afirmaciones sin evidencia (alucinación factual).
- Tasa de incumplimiento de restricciones duras.
- Consistencia ante paráfrasis de la misma oferta.
- Porcentaje de requisitos obligatorios correctamente identificados.

## Reglas de ejecución

- Fijar modelo, versión de prompt y parámetros por corrida.
- Guardar cada salida junto con hash de CV, hash de oferta y timestamp.
- No modificar las etiquetas de referencia para hacer coincidir al modelo.
- Separar ofertas usadas para ajustar prompts de un conjunto reservado para validación.
- No considerar el benchmark aprobado solo por un promedio global: revisar errores críticos individualmente.

## Umbrales

No se fijan umbrales de aprobación hasta obtener una primera línea base. Los límites deben definirse después de revisar los errores de la versión inicial.
