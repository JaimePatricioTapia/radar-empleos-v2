"""Conectores de descubrimiento público de ofertas para Radar 2.0.

No evalúa ofertas ni consume Gemini: solo descubre, normaliza y devuelve avisos.
Los conectores usan páginas/API públicas y respetan timeouts; no automatizan
inicios de sesión ni evaden controles de acceso.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}
TIMEOUT = 18
DETAIL_TIMEOUT = 8
DETAIL_ENRICHMENT_LIMIT = 4
BNE_SEARCH_TIMEOUT = 12
BNE_DETAIL_TIMEOUT = 6


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()



def canonical_job_url(url: str) -> str:
    """Normaliza tracking sin borrar parámetros que identifican una vacante (p. ej. Indeed jk)."""
    parts = urlsplit(str(url or "").strip())
    identity_keys = {"jk", "vjk", "jobid", "job_id", "gh_jid", "reqid", "rid", "jid", "id"}
    identity_params = sorted(
        (key.lower(), value) for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() in identity_keys
    )
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
        urlencode(identity_params), ""
    ))


def normalize_offer(*, source: str, title: str, url: str, company: str = "",
                    location: str = "", description: str = "",
                    published_at: str | None = None, employment_type: str = "",
                    salary_text: str = "", external_id: str = "",
                    raw_metadata: dict | None = None) -> dict | None:
    title, url = clean_text(title), str(url or "").strip()
    if not title or not url.startswith(("https://", "http://")):
        return None
    description = clean_text(description)
    raw_metadata = dict(raw_metadata or {})
    raw_metadata.setdefault("description_quality", "usable" if len(description) >= 150 else "short_or_missing")
    canonical = canonical_job_url(url)
    identity = canonical or "|".join((title.lower(), company.lower(), location.lower(), source))
    job_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return {
        "source": source, "source_url": url, "external_id": str(external_id or "") or None,
        "title": title[:500], "company": clean_text(company)[:300] or None,
        "location": clean_text(location)[:300] or None,
        "employment_type": clean_text(employment_type)[:120] or None,
        "salary_text": clean_text(salary_text)[:200] or None,
        "description": description[:30000] or title,
        "published_at": published_at or None, "job_hash": job_hash,
        "raw_metadata": raw_metadata,
    }


def _extract_published_at(container) -> str | None:
    """Obtiene fechas explícitas de tarjetas HTML sin inferirlas desde el orden."""
    if container is None:
        return None
    selectors = (
        "time[datetime]", "time", "[data-date]", "[data-published]",
        ".date", ".fecha", ".posted", ".publication-date",
    )
    for selector in selectors:
        element = container.select_one(selector)
        if element is None:
            continue
        value = (
            element.get("datetime") or element.get("data-date")
            or element.get("data-published") or element.get_text(" ", strip=True)
        )
        if value:
            return str(value).strip()
    return None


def _request_get(url: str, **kwargs):
    timeout = kwargs.pop("timeout", TIMEOUT)
    return requests.get(url, headers=HEADERS, timeout=timeout, **kwargs)


def search_jobspy_site(query: str, *, site: str, limit: int = 15,
                       location: str = "Chile") -> list[dict]:
    """Consulta un portal JobSpy; Indeed se busca en Chile y Antofagasta.

    Las descripciones se recuperan para Indeed/Glassdoor porque el filtro de
    pertinencia necesita funciones y requisitos, no solo el título. LinkedIn
    mantiene la descarga desactivada para reducir solicitudes sobre un portal
    que ya aplica bloqueos.
    """
    if site not in {"linkedin", "indeed", "glassdoor"}:
        raise ValueError(f"Portal JobSpy no soportado: {site}")

    from jobspy import scrape_jobs

    locations = [location, "Antofagasta, Chile"] if site == "indeed" and location == "Chile" else [location]
    results = []
    errors_seen = []
    seen = set()
    for search_location in dict.fromkeys(locations):
        frame = scrape_jobs(
            site_name=[site],
            search_term=query,
            location=search_location,
            results_wanted=limit,
            hours_old=336,
            country_indeed="Chile",
            fetch_description=site in {"indeed", "glassdoor"},
            verbose=0,
        )
        if frame is None:
            continue

        attrs = getattr(frame, "attrs", {}) or {}
        errors = attrs.get("errors", {}) or {}
        if errors.get(site):
            error = str(errors[site])
            errors_seen.append(f"{search_location}: {error}")
            # Un bloqueo explícito no se debe insistir desde la misma IP.
            if "429" in error or "403" in error:
                break
            continue

        if frame.empty:
            continue

        for row in frame.to_dict(orient="records"):
            source = str(row.get("site") or row.get("source") or site).lower()
            offer = normalize_offer(
                source=source,
                title=row.get("title"),
                url=row.get("job_url") or row.get("link"),
                company=row.get("company_name") or row.get("company"),
                location=row.get("location") or search_location,
                description=row.get("description"),
                published_at=str(row.get("date_posted") or "") or None,
                employment_type=row.get("job_type"),
                salary_text=row.get("min_amount") or row.get("salary"),
                external_id=str(row.get("id") or ""),
                raw_metadata={
                    "via": "python-jobspy",
                    "description_fetch_requested": site in {"indeed", "glassdoor"},
                    "search_location": search_location,
                },
            )
            if offer and offer["job_hash"] not in seen:
                seen.add(offer["job_hash"])
                results.append(offer)

    if errors_seen and not results:
        raise RuntimeError(f"JobSpy {site}: {'; '.join(errors_seen)}")
    return results


def search_linkedin(query: str, limit: int = 15) -> list[dict]:
    """Busca ofertas públicas de LinkedIn sin descargar cada página individual."""
    return search_jobspy_site(query, site="linkedin", limit=limit)


def search_indeed(query: str, limit: int = 15) -> list[dict]:
    """Busca Indeed en Chile y refuerza la cobertura minera en Antofagasta."""
    return search_jobspy_site(query, site="indeed", limit=limit)


def search_glassdoor(query: str, limit: int = 15) -> list[dict]:
    """Busca ofertas públicas de Glassdoor mediante JobSpy."""
    return search_jobspy_site(query, site="glassdoor", limit=limit)

def search_getonbrd(query: str, limit: int = 15) -> list[dict]:
    response = _request_get("https://www.getonbrd.com/api/v0/search/jobs",
                            params={"query": query, "per_page": limit})
    response.raise_for_status()
    results = []
    for item in response.json().get("data", []):
        attrs, links = item.get("attributes") or {}, item.get("links") or {}
        company_data = (attrs.get("company") or {}).get("data") or {}
        company = ((company_data.get("attributes") or {}).get("name")) if isinstance(company_data, dict) else ""
        url = links.get("public_url") or attrs.get("url")
        desc = " ".join((attrs.get("description") or "", attrs.get("functions") or ""))
        offer = normalize_offer(
            source="getonbrd", title=attrs.get("title"), url=url, company=company,
            location="Chile / Remoto" if attrs.get("remote") else attrs.get("country") or "Chile",
            description=desc, published_at=attrs.get("published_at"),
            salary_text=f"{attrs.get('min_salary')} - {attrs.get('max_salary')}" if attrs.get("min_salary") or attrs.get("max_salary") else "",
            external_id=str(item.get("id") or ""),
        )
        if offer:
            results.append(offer)
    return results


def search_chiletrabajos(query: str, limit: int = 12) -> list[dict]:
    response = _request_get("https://www.chiletrabajos.cl/encuentra-un-empleo",
                            params={"f": 2, "q": query})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    # Evitar el fallback genérico a cualquier <article>: varias páginas incluyen
    # artículos editoriales/recomendaciones que no son tarjetas de vacantes.
    for card in soup.select("div.job-item, div.destacado")[:limit]:
        link = card.select_one("h2.title a, h3.title a, a[href*='/trabajo/']")
        if not link:
            continue
        url = urljoin("https://www.chiletrabajos.cl", link.get("href", ""))
        company = card.select_one(".company, .empresa, a[href*='/empresa/']")
        location = card.select_one(".city, .ciudad, a[href*='/ciudad/']")
        summary = card.select_one("p, .text, .description")
        description = summary.get_text(" ", strip=True) if summary else ""
        if len(description) < 120 and url and len(results) < DETAIL_ENRICHMENT_LIMIT:
            try:
                detail = _request_get(url, timeout=DETAIL_TIMEOUT)
                if detail.ok:
                    detail_soup = BeautifulSoup(detail.text, "html.parser")
                    body = detail_soup.select_one(".job-description, .descripcion, [itemprop='description']")
                    if body:
                        description = body.get_text(" ", strip=True)
            except requests.RequestException:
                pass
        offer = normalize_offer(
            source="chiletrabajos", title=link.get_text(" ", strip=True), url=url,
            company=company.get_text(" ", strip=True) if company else "",
            location=location.get_text(" ", strip=True) if location else "Chile",
            description=description, published_at=_extract_published_at(card),
        )
        if offer:
            results.append(offer)
    return results


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_value.lower())).strip("-")


def search_computrabajo(query: str, limit: int = 12) -> list[dict]:
    base = "https://cl.computrabajo.com"
    response = _request_get(f"{base}/trabajo-de-{_slug(query)}")
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for card in soup.select("article.box_offer, div.box_offer")[:limit]:
        link = card.select_one("h2 a, h1 a, a.js-o-link")
        if not link:
            continue
        company = card.select_one("[class*='company'], p[class*='fc_base'], .fs16")
        location = card.select_one("[class*='location'], p[class*='fs13'], span[class*='city']")
        summary = card.select_one("p:not([class*='fc_base'])")
        offer = normalize_offer(
            source="computrabajo", title=link.get_text(" ", strip=True),
            url=urljoin(base, link.get("href", "")),
            company=company.get_text(" ", strip=True) if company else "",
            location=location.get_text(" ", strip=True) if location else "Chile",
            description=summary.get_text(" ", strip=True) if summary else "",
            published_at=_extract_published_at(card),
        )
        if offer:
            results.append(offer)
    return results


def search_contutalento(query: str, limit: int = 12) -> list[dict]:
    base = "https://contutalento.cl/laboral/"
    response = _request_get(base, params={"s": query})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results, seen = [], set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        link = heading.find("a") or heading.find_parent("a")
        if not link or not link.get("href"):
            continue
        url = urljoin(base, link["href"])
        if "/laboral/" not in url or url.rstrip("/") == base.rstrip("/") or url in seen:
            continue
        seen.add(url)
        text = heading.get_text(" ", strip=True)
        company, title = "Red Compromiso Minero", text
        for separator in ("–", "-", "—", "|"):
            if separator in text:
                company, title = [part.strip() for part in text.split(separator, 1)]
                break
        offer = normalize_offer(
            source="contutalento", title=title, url=url, company=company,
            location="Chile", description="",
            published_at=_extract_published_at(heading.find_parent(["article", "li", "div"])),
            raw_metadata={"description_status": "pendiente de enriquecimiento"},
        )
        if offer:
            results.append(offer)
        if len(results) >= limit:
            break
    return results


def search_bne(query: str, limit: int = 12) -> list[dict]:
    headers = {**HEADERS, "Accept": "application/json, text/plain, */*", "Content-Type": "application/json"}
    response = requests.post(
        "https://www.bne.cl/api/ofertas/busqueda", params={"page": 0, "size": limit},
        json={"textoBusqueda": query}, headers=headers, timeout=BNE_SEARCH_TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("content", []):
        offer_id = item.get("id")
        if not offer_id:
            continue
        employer, region, commune = item.get("empresario") or {}, item.get("region") or {}, item.get("comuna") or {}
        schedule = item.get("jornadaLaboral") or {}
        description = str(item.get("descripcion") or "")
        if len(description) < 150 and len(results) < DETAIL_ENRICHMENT_LIMIT:
            try:
                detail = requests.get(f"https://www.bne.cl/api/ofertas/publica/{offer_id}",
                                      headers=headers, timeout=BNE_DETAIL_TIMEOUT)
                if detail.ok:
                    description = str(detail.json().get("descripcion") or description)
            except requests.RequestException:
                pass
        offer = normalize_offer(
            source="bne", title=item.get("nombrePuesto"), url=f"https://www.bne.cl/ofertas/{offer_id}",
            company=employer.get("nombreComercial") or "Empresa registrada BNE",
            location=", ".join(x for x in (commune.get("nombre"), region.get("nombre")) if x) or "Chile",
            description=description, published_at=item.get("fechaPublicacion"),
            employment_type=schedule.get("nombre"), external_id=str(offer_id),
        )
        if offer:
            results.append(offer)
    return results


def search_codelco(query: str, limit: int = 12) -> list[dict]:
    base = "https://empleos.codelco.cl"
    response = _request_get(f"{base}/search/", params={"q": query, "locale": "es_ES"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for link in soup.select('a[href*="/job/"]'):
        title = link.get_text(" ", strip=True)
        if len(title) < 5:
            continue
        row = link.find_parent("tr")
        offer = normalize_offer(
            source="codelco", title=title, url=urljoin(base, link.get("href", "")),
            company="Codelco", location=row.get_text(" ", strip=True) if row else "Chile",
            description="",
            published_at=_extract_published_at(row or link.parent),
        )
        if offer:
            results.append(offer)
        if len(results) >= limit:
            break
    return results


def search_finning(query: str, limit: int = 12) -> list[dict]:
    api = "https://finning.wd3.myworkdayjobs.com/wday/cxs/finning/External/jobs"
    public = "https://finning.wd3.myworkdayjobs.com/en-US/External"
    response = requests.post(
        api, json={"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": query},
        headers={**HEADERS, "Accept": "application/json", "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    results = []
    for posting in response.json().get("jobPostings", []):
        path = posting.get("externalPath")
        if not path:
            continue
        offer = normalize_offer(
            source="finning", title=posting.get("title"), url=urljoin(public + "/", path.lstrip("/")),
            company="Finning", location=posting.get("locationsText") or "Chile / Sudamérica",
            description=" ".join(map(str, posting.get("bulletFields") or [])),
            published_at=posting.get("postedOn"),
        )
        if offer:
            results.append(offer)
    return results


SOURCE_REGISTRY = {
    # Google Jobs se excluye: JobSpy 1.5.0 lo reporta actualmente no disponible.
    "linkedin": ("LinkedIn", "linkedin"), "indeed": ("Indeed", "indeed"),
    "glassdoor": ("Glassdoor", "glassdoor"),
    "getonbrd": ("Get on Board", "getonbrd"),
    "chiletrabajos": ("Chiletrabajos", "chiletrabajos"),
    "computrabajo": ("Computrabajo", "computrabajo"),
    "contutalento": ("Con tu Talento", "contutalento"),
    "bne": ("Bolsa Nacional de Empleo", "bne"),
    "codelco": ("Codelco Empleos", "codelco"),
    "finning": ("Finning Careers", "finning"),
}
CONNECTORS = {
    "linkedin": search_linkedin, "indeed": search_indeed,
    "glassdoor": search_glassdoor,
    "getonbrd": search_getonbrd,
    "chiletrabajos": search_chiletrabajos, "computrabajo": search_computrabajo,
    "contutalento": search_contutalento, "bne": search_bne,
    "codelco": search_codelco, "finning": search_finning,
}
