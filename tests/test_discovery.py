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


def test_relative_published_date_is_parsed_without_fabricating_unknown_dates():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    assert _parse_published_at("hace 3 días", now=now) == "2026-11-20T12:00:00+00:00"
    assert _parse_published_at("hace 2 meses", now=now) == "2026-09-24T12:00:00+00:00"
    assert _parse_published_at("fecha desconocida", now=now) is None


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
    assert kwargs["hours_old"] == 336
    assert "linkedin_fetch_description" not in kwargs


def test_indeed_searches_chile_and_antofagasta_and_fetches_descriptions(monkeypatch):
    def frame_for(job_id):
        return SimpleNamespace(
            attrs={},
            empty=False,
            to_dict=lambda orient: [{
                "site": "indeed",
                "title": f"Analista Funcional {job_id}",
                "job_url": f"https://cl.indeed.com/viewjob?jk={job_id}",
                "company_name": "Empresa",
                "description": "Levantamiento de requerimientos, procesos y proyectos TI.",
            }],
        )

    scrape = Mock(side_effect=[frame_for("a1"), frame_for("a2")])
    monkeypatch.setitem(sys.modules, "jobspy", SimpleNamespace(scrape_jobs=scrape))

    offers = search_jobspy_site("Analista Funcional", site="indeed", limit=15)

    assert len(offers) == 2
    assert [call.kwargs["location"] for call in scrape.call_args_list] == [
        "Chile", "Antofagasta, Chile"
    ]
    assert all(call.kwargs["fetch_description"] is True for call in scrape.call_args_list)
    assert offers[1]["raw_metadata"]["search_location"] == "Antofagasta, Chile"


def test_glassdoor_is_registered_as_an_independent_jobspy_source():
    from src.search.sources import CONNECTORS, SOURCE_REGISTRY
    assert SOURCE_REGISTRY["glassdoor"][1] == "glassdoor"
    assert callable(CONNECTORS["glassdoor"])


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
    assert SOURCE_REGISTRY["glassdoor"][1] == "glassdoor"
    assert CONNECTORS["linkedin"] is not CONNECTORS["indeed"]
    assert "google" not in SOURCE_REGISTRY


def test_run_discovery_does_not_repeat_linkedin_for_each_selected_jobspy_source(monkeypatch):
    from src.search import ingestion

    linkedin = Mock(return_value=[])
    indeed = Mock(return_value=[])
    monkeypatch.setitem(ingestion.CONNECTORS, "linkedin", linkedin)
    monkeypatch.setitem(ingestion.CONNECTORS, "indeed", indeed)

    result = ingestion.run_discovery(
        client=object(),
        user_id="user-1",
        roles=["Business Analyst", "Analista Funcional", "Project Manager"],
        sources=["linkedin", "indeed"],
    )

    assert linkedin.call_count == 1
    assert linkedin.call_args.kwargs["limit"] == 25
    assert indeed.call_count == 3
    assert result["queries"] == 4
    assert result["errors"] == 0


def test_domain_terms_do_not_narrow_the_actual_search_query(monkeypatch):
    from src.search import ingestion

    connector = Mock(return_value=[])
    monkeypatch.setitem(ingestion.CONNECTORS, "getonbrd", connector)
    family = {
        "family_id": "business_analysis",
        "family_name": "Análisis de negocio y procesos",
        "priority": 1,
        "titles": ["Business Analyst"],
        "domain_terms": ["requerimientos", "historias de usuario", "procesos"],
        "evidence": ["business analyst", "PBI"],
    }

    ingestion.run_discovery(
        client=object(),
        user_id="user-1",
        roles=["Business Analyst"],
        sources=["getonbrd"],
        role_context=[family],
    )

    assert connector.call_args.args[0] == "Business Analyst"


def test_linkedin_failure_does_not_stop_other_portals(monkeypatch):
    from src.search import ingestion

    linkedin = Mock(side_effect=RuntimeError("429 blocked"))
    indeed = Mock(return_value=[])
    monkeypatch.setitem(ingestion.CONNECTORS, "linkedin", linkedin)
    monkeypatch.setitem(ingestion.CONNECTORS, "indeed", indeed)

    result = ingestion.run_discovery(
        client=object(),
        user_id="user-1",
        roles=["Business Analyst", "Analista Funcional"],
        sources=["linkedin", "indeed"],
    )

    assert linkedin.call_count == 1
    assert indeed.call_count == 2
    assert result["errors"] == 1
    assert result["by_source"]["indeed"]["errors"] == 0



def test_english_relative_publication_dates_are_parsed():
    from datetime import datetime, timezone
    now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
    assert _parse_published_at("2 days ago", now=now) == "2026-11-21T12:00:00+00:00"


class _EmptyQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=[])


class _EmptyClient:
    def table(self, _name):
        return _EmptyQuery()


def test_discovery_discards_explicitly_old_offers_and_emits_saved_offer(monkeypatch):
    from src.search import ingestion

    now_recent = "hace 2 días"
    old = "hace 20 días"
    connector = Mock(return_value=[
        {"title": "Business Analyst reciente", "company": "Empresa A",
         "source": "linkedin", "source_url": "https://example.com/recent",
         "published_at": now_recent, "description": "Descripción"},
        {"title": "Business Analyst antiguo", "company": "Empresa B",
         "source": "linkedin", "source_url": "https://example.com/old",
         "published_at": old, "description": "Descripción"},
        {"title": "Business Analyst sin fecha", "company": "Empresa C",
         "source": "linkedin", "source_url": "https://example.com/unknown",
         "published_at": None, "description": "Descripción"},
    ])
    monkeypatch.setitem(ingestion.CONNECTORS, "linkedin", connector)
    monkeypatch.setattr(ingestion, "upsert_job_offer", lambda _client, user_id, offer: {
        "id": offer["source_url"], "title": offer["title"], "company": offer["company"],
        "location": None, "source": "linkedin", "source_url": offer["source_url"],
        "published_at": offer.get("published_at"),
    })
    emitted = []

    result = ingestion.run_discovery(
        _EmptyClient(), user_id="user-1", roles=["Business Analyst"],
        sources=["linkedin"], on_offer=emitted.append,
    )

    assert result["saved"] == 2
    assert result["stale_skipped"] == 1
    assert result["publication_date_unknown"] == 1
    assert len(emitted) == 2
    assert emitted[1]["publication_date_status"] == "unknown"


def test_discovery_stop_finishes_current_query_and_skips_next_queries(monkeypatch):
    from threading import Event
    from src.search import ingestion

    stop = Event()
    linkedin = Mock(side_effect=lambda *_args, **_kwargs: (stop.set() or []))
    indeed = Mock(return_value=[])
    monkeypatch.setitem(ingestion.CONNECTORS, "linkedin", linkedin)
    monkeypatch.setitem(ingestion.CONNECTORS, "indeed", indeed)
    progress = []

    result = ingestion.run_discovery(
        _EmptyClient(), user_id="user-1",
        roles=["Business Analyst", "Analista Funcional"],
        sources=["linkedin", "indeed"],
        should_stop=stop.is_set, on_progress=progress.append,
    )

    assert result["stopped_early"] is True
    assert result["queries_completed"] == 1
    assert linkedin.call_count == 1
    assert indeed.call_count == 0
    assert progress[-1]["queries_completed"] == 1



def test_html_publication_date_extractor_reads_explicit_date():
    from bs4 import BeautifulSoup
    from src.search.sources import _extract_published_at

    card = BeautifulSoup(
        '<article><time datetime="2026-11-22T09:00:00Z">Publicado ayer</time></article>',
        "html.parser",
    ).article
    assert _extract_published_at(card) == "2026-11-22T09:00:00Z"



def test_source_circuit_breaker_skips_remaining_queries_after_two_consecutive_errors(monkeypatch):
    from src.search import ingestion

    bne = Mock(side_effect=RuntimeError("BNE timeout"))
    monkeypatch.setitem(ingestion.CONNECTORS, "bne", bne)
    progress = []
    result = ingestion.run_discovery(
        _EmptyClient(), user_id="user-1",
        roles=["Business Analyst", "Analista Funcional", "Project Manager"],
        sources=["bne"], on_progress=progress.append,
    )

    assert bne.call_count == 2
    assert result["errors"] == 2
    assert result["queries_completed"] == 2
    assert result["queries_skipped"] == 1
    assert result["by_source"]["bne"]["skipped_queries"] == 1
    assert progress[-1]["status"] == "source_skipped"
