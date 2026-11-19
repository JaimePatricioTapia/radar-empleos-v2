import pytest
from src.cv.embeddings import embed_texts


def test_embeddings_reject_empty_text():
    with pytest.raises(ValueError, match="vacíos"):
        embed_texts([""], api_key="fake")


def test_embeddings_fix_dimensions():
    with pytest.raises(ValueError, match="3.072"):
        embed_texts(["texto"], api_key="fake", output_dimensionality=768)
