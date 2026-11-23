import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.search.ingestion import _parse_published_at, _queries_for_source, _stable_hash
from src.search.sources import CONNECTORS, SOURCE_REGISTRY, normalize_offer, search_jobspy_site


def test_normalize_offer_requires_real_title_and_http_url():
    assert normalize_offer(source="test", title="", url="https://example.com/job") is None
    assert normalize_offer(source="test", title="Analista", url="not-a-url") is None


def test_normalize_offer_produces_expected_fields():
    offer = normalize_offer(source="test", title="  Business Analyst ",
                            url="https://example.com/jobs/123", company="Empresa",
                            description="<p>Levantamiento de requisitos</p>")
    assert offer["title"] == "Business Analyst"
    assert offer["description"] == "Levantamiento de requisitos"
    assert len(offer["job_hash"]) == 64
    assert offer["source_url"] == "https://example.com/jobs/123"


def test_hash_is_stable_for_same_canonical_url():
    a = {"source_url": "https://example.com/job/1?utm=abc", "title": "X", "source": "one"}
    b = {"source_url": "https://example.com/job/1?utm=xyz", "title": "Y", "source": "two"}
    assert _stable_hash(a) == _stable_hash(b)


def test_relative_published_date_is_not_fabricated():
    assert _parse_published_at("hace 3 días") is None


def test_iso_published_date_is_normalized():
    assert _parse_published_at("2026-11-19T10:00:00Z") == "2026-11-19T10:00:00+00:00"


def test_jobspy_calls_only_the_requested_portal_and_does_not_fetch_details(monkeypatch):
    frame = SimpleNamespace(
        attrs={},
        empty=False,
        to_dict=lambda orient: [{
            "site": "linkedin",
            "title": "Business Analyst",
            "job_url": "https://www.linkedin.com/jobs/view/123",
            "company_name": "Empresa",
            "description": "Levantamiento de requisitos y gestión de proyectos.",
        }],
    )
    scrape = Mock(return_value=frame)
    monkeypatch.setitem(sys.modules, "jobspy", SimpleNamespace(scrape_jobs=scrape))

    offers = search_jobspy_site("Business Analyst", site="linkedin", limit=20)

    assert len(offers) == 1
    assert offers[0]["source"] == "linkedin"
    kwargs = scrape.call_args.kwargs
    assert kwargs["site_name"] == ["linkedin"]
    assert kwargs["fetch_description"] is False
    assert "linkedin_fetch_description" not in kwargs


def test_jobspy_surfaces_source_errors_instead_of_silently_returning_empty(monkeypatch):
    frame = SimpleNamespace(
        attrs={"errors": {"linkedin": "response status code 429 (blocked: use a proxy)"}},
        empty=True,
        to_dict=lambda orient: [],
    )
    monkeypatch.setitem(
        sys.modules, "jobspy",
        SimpleNamespace(scrape_jobs=Mock(return_value=frame)),
    )

    with pytest.raises(RuntimeError, match="429"):
        search_jobspy_site("Business Analyst", site="linkedin")


def test_linkedin_is_one_grouped_query_and_indeed_remains_per_role():
    roles = ["Business Analyst", "Analista Funcional", "Project Manager"]
    linkedin_queries = _queries_for_source("linkedin", roles)
    indeed_queries = _queries_for_source("indeed", roles)

    assert len(linkedin_queries) == 1
    assert '"Business Analyst" OR "Analista Funcional" OR "Project Manager"' in linkedin_queries[0][0]
    assert len(indeed_queries) == len(roles)
    assert [label for _, label in indeed_queries] == roles


def test_jobspy_sources_are_independent_and_google_jobs_is_not_advertised():
    assert SOURCE_REGISTRY["linkedin"][1] == "linkedin"
    assert SOURCE_REGISTRY["indeed"][1] == "indeed"
    assert CONNECTORS["linkedin"] is not CONNECTORS["indeed"]
    assert "google" not in SOURCE_REGISTRY
