from src.search.salary import analyse_salary, attractiveness_score


def test_missing_salary_is_not_penalised():
    result = analyse_salary(None)
    assert result["status"] == "unknown"
    assert result["adjustment"] == 0


def test_liquid_salary_below_preference_reduces_attractiveness_only():
    result = analyse_salary("$850.000 líquidos")
    assert result["status"] == "below_preference"
    assert result["adjustment"] == -10
    assert attractiveness_score(92, result) == 82


def test_liquid_salary_at_preference_has_no_penalty():
    result = analyse_salary("$1.200.000 líquidos")
    assert result["status"] == "meets_preference"
    assert result["adjustment"] == 0


def test_gross_salary_is_not_compared_to_liquid_preference():
    result = analyse_salary("$1.500.000 bruto")
    assert result["status"] == "not_comparable"
    assert result["adjustment"] == 0


def test_salary_range_crossing_preference_gets_moderate_adjustment():
    result = analyse_salary("$900.000 a $1.200.000 líquidos")
    assert result["status"] == "range_crosses_preference"
    assert result["adjustment"] == -5
