import pytest
from src.evaluation.metrics import classification_report, mean_absolute_error, agreement_rate


def test_classification_report_perfect_predictions():
    labels = ["POSTULAR", "POSTULAR CON RESERVAS", "DESCARTAR"]
    report = classification_report(labels, labels)
    assert report["accuracy"] == 1.0
    assert report["macro_f1"] == 1.0


def test_classification_report_rejects_different_lengths():
    with pytest.raises(ValueError):
        classification_report(["POSTULAR"], [])


def test_mae():
    assert mean_absolute_error([80, 60, 20], [70, 60, 30]) == pytest.approx(20 / 3)


def test_agreement_rate():
    assert agreement_rate(["POSTULAR", "POSTULAR", "DESCARTAR"]) == pytest.approx(2 / 3)
