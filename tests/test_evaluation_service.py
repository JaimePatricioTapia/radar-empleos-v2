import pytest
from src.evaluation.service import evaluate_job_offer


def test_offer_evaluation_requires_title_and_description():
    with pytest.raises(ValueError, match="cargo y descripción"):
        evaluate_job_offer({"title": "", "description": ""}, client=object(), user_id="user-1")
