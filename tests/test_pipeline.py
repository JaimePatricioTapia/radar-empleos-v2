from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.cv.embeddings import EmbeddingRateLimitError

from src.search import pipeline


class _Query:
    def __init__(self, data):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return MagicMock(data=self.data)


class _Client:
    def __init__(self, cv_rows=None):
        self.cv_rows = cv_rows if cv_rows is not None else [{"id": "cv-active"}]

    def table(self, name):
        assert name == "cv_versions"
        return _Query(self.cv_rows)


def test_full_pipeline_runs_discovery_preparation_until_empty_and_evaluation():
    client = _Client()
    progress = []

    with (
        patch.object(pipeline, "run_discovery", return_value={
            "total_found": 12, "saved": 10, "duplicates": 2,
            "by_source": {}, "error_details": [],
        }) as discovery,
        patch.object(pipeline, "get_processing_status", side_effect=[
            {"pending_chunking": 2},
            {"pending_chunking": 1},
            {"pending_chunking": 1},
            {"pending_chunking": 0},
            {"pending_chunking": 0},
            {"pending_chunking": 0},
        ]),
        patch.object(pipeline, "build_job_chunks", side_effect=[
            {"offers_chunked": 1, "chunks_saved": 3, "insufficient": 0, "excluded": 0},
            {"offers_chunked": 1, "chunks_saved": 2, "insufficient": 0, "excluded": 0},
        ]) as chunking,
        patch.object(pipeline, "evaluate_top_offers", return_value={
            "ranked": 2, "evaluated": 2, "below_threshold": 1,
            "skipped_existing": 0, "skipped_excluded": 0,
            "errors": [], "results": [],
        }) as evaluation,
    ):
        result = pipeline.run_full_search_pipeline(
            client, user_id="user-1", roles=["Business Analyst"],
            sources=["linkedin"], progress=progress.append,
        )

    discovery.assert_called_once()
    assert chunking.call_count == 2
    evaluation.assert_called_once()
    assert result["completed"] is True
    assert result["preparation"]["offers_chunked"] == 2
    assert result["evaluation"]["evaluated"] == 2
    assert any("Etapa 1/3" in message for message in progress)
    assert any("Etapa 3/3" in message for message in progress)


def test_full_pipeline_requires_an_active_cv_before_searching():
    with patch.object(pipeline, "run_discovery") as discovery:
        with pytest.raises(ValueError, match="currículum"):
            pipeline.run_full_search_pipeline(
                _Client(cv_rows=[]), user_id="user-1",
                roles=["Business Analyst"], sources=["linkedin"],
            )
    discovery.assert_not_called()


def test_full_pipeline_stops_if_chunking_does_not_make_progress():
    client = _Client()
    with (
        patch.object(pipeline, "run_discovery", return_value={"total_found": 1}),
        patch.object(pipeline, "get_processing_status", side_effect=[
            {"pending_chunking": 1},
            {"pending_chunking": 1},
        ]),
        patch.object(pipeline, "build_job_chunks", return_value={
            "offers_chunked": 0, "chunks_saved": 0,
        }),
    ):
        with pytest.raises(RuntimeError, match="sin avanzar"):
            pipeline.run_full_search_pipeline(
                client, user_id="user-1",
                roles=["Business Analyst"], sources=["linkedin"],
            )


def test_affinity_recommendation_threshold_is_85():
    from src.search.processing import meets_affinity_threshold

    assert meets_affinity_threshold(85) is True
    assert meets_affinity_threshold(84) is False
    assert meets_affinity_threshold(None) is False



def test_full_pipeline_pauses_cleanly_when_embedding_quota_stays_exhausted():
    client = _Client()
    with (
        patch.object(pipeline, "get_settings", return_value=SimpleNamespace(
            max_daily_job_chunks=250, max_daily_evaluations=15
        )),
        patch.object(pipeline, "run_discovery", return_value={
            "total_found": 1, "saved": 1, "errors": 0,
            "by_source": {}, "error_details": [],
        }),
        patch.object(pipeline, "get_processing_status", side_effect=[
            {"pending_chunking": 1, "daily_chunk_budget_remaining": 250},
            {"pending_chunking": 1, "daily_chunk_budget_remaining": 249},
        ]),
        patch.object(
            pipeline, "build_job_chunks",
            side_effect=EmbeddingRateLimitError("429 RESOURCE_EXHAUSTED", 51),
        ),
        patch.object(pipeline, "evaluate_top_offers", return_value={
            "ranked": 0, "evaluated": 0, "below_threshold": 0,
            "skipped_existing": 0, "skipped_excluded": 0,
            "errors": [], "results": [], "budget_exhausted": False,
            "budget_remaining": 15,
        }),
    ):
        result = pipeline.run_full_search_pipeline(
            client, user_id="user-1",
            roles=["Business Analyst"], sources=["linkedin"],
        )

    assert result["paused_for_api_quota"] is True
    assert result["completed"] is False
    assert result["preparation"]["pending_remaining"] == 1
    assert "429" in result["preparation"]["api_quota_message"]
