from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.search import ingestion, sources


def test_custom_portal_uses_query_placeholder_and_extracts_public_job_links(monkeypatch):
    monkeypatch.setattr(
        sources.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    response = SimpleNamespace(
        url="https://jobs.example.org/search?q=Business+Analyst",
        text="""
        <html><body>
          <div class="job-card">
            <a href="/jobs/123">Business Analyst Senior</a>
            <p>Levantamiento de requisitos, análisis funcional y coordinación de proyectos TI.</p>
            <time datetime="2026-11-24">Publicado</time>
          </div>
        </body></html>
        """,
        raise_for_status=lambda: None,
        status_code=200,
    )
    request = Mock(return_value=response)
    monkeypatch.setattr(sources, "_request_get", request)

    offers = sources.search_custom_portal(
        "Business Analyst",
        portal={
            "id": "custom_portal_1",
            "name": "Portal de prueba",
            "url_template": "https://jobs.example.org/search?q={query}",
        },
        limit=10,
    )

    assert request.call_args.args[0] == "https://jobs.example.org/search?q=Business+Analyst"
    assert len(offers) == 1
    assert offers[0]["title"] == "Business Analyst Senior"
    assert offers[0]["source"] == "custom_portal_1"
    assert offers[0]["source_url"] == "https://jobs.example.org/jobs/123"
    assert offers[0]["raw_metadata"]["custom_portal"] is True


def test_custom_portal_rejects_private_hosts(monkeypatch):
    monkeypatch.setattr(
        sources.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(ValueError, match="dominio público"):
        sources._validate_public_portal_url("https://internal.example/jobs")


def test_custom_portal_requires_http_scheme():
    with pytest.raises(ValueError, match="https"):
        sources._validate_public_portal_url("file:///etc/passwd")


def test_discovery_executes_user_added_portal(monkeypatch):
    custom_search = Mock(return_value=[])
    monkeypatch.setattr(ingestion, "search_custom_portal", custom_search)
    portal = {
        "id": "custom_portal_1",
        "name": "Portal Minero",
        "url_template": "https://jobs.example.org/search?q={query}",
    }

    result = ingestion.run_discovery(
        client=object(),
        user_id="user-1",
        roles=["Analista de Contratos Mineros"],
        sources=["custom_portal_1"],
        custom_sources=[portal],
    )

    custom_search.assert_called_once_with(
        "Analista de Contratos Mineros",
        portal=portal,
        limit=12,
    )
    assert result["queries"] == 1
    assert result["errors"] == 0


def test_discovery_rejects_unknown_custom_source_without_configuration():
    with pytest.raises(ValueError, match="Fuentes no reconocidas"):
        ingestion.run_discovery(
            client=object(),
            user_id="user-1",
            roles=["Business Analyst"],
            sources=["custom_portal_1"],
        )
