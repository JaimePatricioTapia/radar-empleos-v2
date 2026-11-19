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
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}
TIMEOUT = 18


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


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
    canonical = url.split("?")[0].rstrip("/").lower()
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


def _request_get(url: str, **kwargs):
    return requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)


def search_jobspy(query: str, limit: int = 15, location: str = "Chile") -> list[dict]:
    """LinkedIn, Indeed y Google Jobs a través de python-jobspy."""
    from jobspy import scrape_jobs
    frame = scrape_jobs(
        site_name=["linkedin", "indeed", "google"], search_term=query,
        location=location, results_wanted=limit, country_indeed="Chile",
        linkedin_fetch_description=True,
    )
    results = []
    if frame is None or frame.empty:
        return results
    for row in frame.to_dict(orient="records"):
        source = str(row.get("site") or row.get("source") or "jobspy").lower()
        offer = normalize_offer(
            source=source, title=row.get("title"), url=row.get("job_url") or row.get("link"),
            company=row.get("company_name") or row.get("company"), location=row.get("location"),
            description=row.get("description"), published_at=str(row.get("date_posted") or "") or None,
            employment_type=row.get("job_type"), salary_text=row.get("min_amount") or row.get("salary"),
            raw_metadata={"via": "python-jobspy"},
        )
        if offer:
            results.append(offer)
    return results


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
    for card in soup.select("div.job-item, div.destacado, article")[:limit]:
        link = card.select_one("h2.title a, h3.title a, a[href*='/trabajo/']")
        if not link:
            continue
        url = urljoin("https://www.chiletrabajos.cl", link.get("href", ""))
        company = card.select_one(".company, .empresa, a[href*='/empresa/']")
        location = card.select_one(".city, .ciudad, a[href*='/ciudad/']")
        summary = card.select_one("p, .text, .description")
        description = summary.get_text(" ", strip=True) if summary else ""
        if len(description) < 120 and url:
            try:
                detail = _request_get(url)
                if detail.ok:
                    detail_soup = BeautifulSoup(detail.text, "html.parser")
                    body = detail_soup.select_one(".job-description, .descripcion, article, .content")
                    if body:
                        description = body.get_text(" ", strip=True)
            except requests.RequestException:
                pass
        offer = normalize_offer(
            source="chiletrabajos", title=link.get_text(" ", strip=True), url=url,
            company=company.get_text(" ", strip=True) if company else "",
            location=location.get_text(" ", strip=True) if location else "Chile",
            description=description,
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
        json={"textoBusqueda": query}, headers=headers, timeout=TIMEOUT,
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
        if len(description) < 150:
            try:
                detail = requests.get(f"https://www.bne.cl/api/ofertas/publica/{offer_id}",
                                      headers=headers, timeout=10)
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
    "linkedin": ("LinkedIn", "jobspy"), "indeed": ("Indeed", "jobspy"),
    "google": ("Google Jobs", "jobspy"), "getonbrd": ("Get on Board", "getonbrd"),
    "chiletrabajos": ("Chiletrabajos", "chiletrabajos"),
    "computrabajo": ("Computrabajo", "computrabajo"),
    "contutalento": ("Con tu Talento", "contutalento"),
    "bne": ("Bolsa Nacional de Empleo", "bne"),
    "codelco": ("Codelco Empleos", "codelco"),
    "finning": ("Finning Careers", "finning"),
}
CONNECTORS = {
    "jobspy": search_jobspy, "getonbrd": search_getonbrd,
    "chiletrabajos": search_chiletrabajos, "computrabajo": search_computrabajo,
    "contutalento": search_contutalento, "bne": search_bne,
    "codelco": search_codelco, "finning": search_finning,
}
