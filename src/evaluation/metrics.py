"""Métricas locales para comparar evaluaciones con referencias humanas."""
from __future__ import annotations
from collections import Counter
from typing import Iterable

LABELS = ("POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR")


def classification_report(y_true: Iterable[str], y_pred: Iterable[str]) -> dict:
    true, pred = list(y_true), list(y_pred)
    if len(true) != len(pred):
        raise ValueError("y_true y y_pred deben tener la misma longitud.")
    if not true:
        raise ValueError("Se requiere al menos un caso para evaluar.")
    matrix = {label: {p: 0 for p in LABELS} for label in LABELS}
    for actual, predicted in zip(true, pred):
        if actual not in LABELS or predicted not in LABELS:
            raise ValueError("Etiqueta de veredicto desconocida.")
        matrix[actual][predicted] += 1
    per_class = {}
    f1_values = []
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[label].values())}
        f1_values.append(f1)
    accuracy = sum(matrix[label][label] for label in LABELS) / len(true)
    return {"accuracy": accuracy, "macro_f1": sum(f1_values) / len(f1_values), "confusion_matrix": matrix, "per_class": per_class}


def mean_absolute_error(expected: Iterable[float], actual: Iterable[float]) -> float:
    expected_list, actual_list = list(expected), list(actual)
    if len(expected_list) != len(actual_list) or not expected_list:
        raise ValueError("Las listas deben tener igual longitud y no estar vacías.")
    return sum(abs(a - b) for a, b in zip(expected_list, actual_list)) / len(expected_list)


def agreement_rate(predictions: Iterable[str]) -> float:
    values = list(predictions)
    if not values:
        raise ValueError("Se requiere al menos una predicción.")
    counts = Counter(values)
    return counts.most_common(1)[0][1] / len(values)
