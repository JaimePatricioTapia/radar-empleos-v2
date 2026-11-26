from types import SimpleNamespace

from src.search import catalog_validation as validation


def _response(status=200, body=None, url="https://jobs.example.cl/search?q=Analista"):
    return SimpleNamespace(
        status_code=status,
        url=url,
        headers={"Content-Type": "text/html; charset=utf-8"},
        text=body or """
        <html><head><title>Empleos</title></head><body>
          <h1>Resultados para Analista</h1>
          <div class="job"><a href="/jobs/123">Analista de Proyectos TI</a>
          <p>Oferta de trabajo publicada</p></div>
        </body></html>
        """,
        raise_for_status=lambda: (_ for _ in ()).throw(RuntimeError("HTTP error")) if status >= 400 else None,
    )


def test_portal_candidate_is_approved_only_after_public_search_test(monkeypatch):
    monkeypatch.setattr(validation.sources, "_validate_public_portal_url", lambda _url: _url)
    monkeypatch.setattr(validation.sources, "_request_get", lambda *_a, **_k: _response())
    result = validation.evaluate_portal_candidate(
        "Portal de empleos", "https://jobs.example.cl/search?q={query}"
    )
    assert result["approved"] is True
    assert result["http_status"] == 200


def test_portal_candidate_rejects_same_domain_as_existing_portal(monkeypatch):
    monkeypatch.setattr(validation.sources, "_validate_public_portal_url", lambda _url: _url)
    result = validation.evaluate_portal_candidate(
        "Otra URL", "https://www.jobs.example.cl/careers",
        existing_portals=[{"name": "Portal existente", "url_template": "https://jobs.example.cl/search"}],
        builtin_domains={},
    )
    assert result["approved"] is False
    assert result["duplicate"] is True
    assert "mismo portal" in result["reason"]


def test_portal_candidate_rejects_builtin_portal_domain(monkeypatch):
    monkeypatch.setattr(validation.sources, "_validate_public_portal_url", lambda _url: _url)
    result = validation.evaluate_portal_candidate(
        "LinkedIn alternativo", "https://www.linkedin.com/jobs/search"
    )
    assert result["approved"] is False
    assert result["duplicate"] is True


def test_portal_candidate_rejects_access_block(monkeypatch):
    monkeypatch.setattr(validation.sources, "_validate_public_portal_url", lambda _url: _url)
    monkeypatch.setattr(
        validation.sources, "_request_get",
        lambda *_a, **_k: _response(status=403),
    )
    result = validation.evaluate_portal_candidate(
        "Portal bloqueado", "https://jobs.example.cl/search?q={query}",
        builtin_domains={},
    )
    assert result["approved"] is False
    assert "HTTP 403" in result["reason"]


def test_portal_candidate_rejects_captcha(monkeypatch):
    monkeypatch.setattr(validation.sources, "_validate_public_portal_url", lambda _url: _url)
    monkeypatch.setattr(
        validation.sources, "_request_get",
        lambda *_a, **_k: _response(body="<html><body>Verify you are human CAPTCHA</body></html>"),
    )
    result = validation.evaluate_portal_candidate(
        "Portal con captcha", "https://jobs.example.cl/search?q={query}",
        builtin_domains={},
    )
    assert result["approved"] is False
    assert "CAPTCHA" in result["reason"]


def test_search_terms_are_normalized_and_deduplicated_before_approval():
    result = validation.validate_new_search_terms(
        ["  Business Analyst  ", "business analyst", "Analista de Datos", "https://malicioso.cl"],
        existing_terms=["analista de datos"],
    )
    assert result["accepted"] == ["Business Analyst"]
    assert result["duplicates"] == ["business analyst", "Analista de Datos"]
    assert result["rejected"][0]["term"] == "https://malicioso.cl"
