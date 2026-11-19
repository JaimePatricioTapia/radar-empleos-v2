import pytest
from src.search.retriever import retrieve_cv_evidence


def test_retriever_rejects_empty_query_before_external_calls():
    with pytest.raises(ValueError, match="no puede estar vacía"):
        retrieve_cv_evidence("", client=object(), api_key="fake")


def test_retriever_rejects_invalid_limit_before_external_calls():
    with pytest.raises(ValueError, match="entre 1 y 50"):
        retrieve_cv_evidence("experiencia minera", client=object(), api_key="fake", limit=100)
