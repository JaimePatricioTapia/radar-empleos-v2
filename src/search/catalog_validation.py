"""Validación previa para incorporar portales y términos al catálogo del usuario."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src.search import sources


BUILTIN_PORTAL_DOMAINS = {
    "linkedin.com": "LinkedIn",
    "indeed.com": "Indeed",
    "glassdoor.com": "Glassdoor",
    "getonbrd.com": "Get on Board",
    "chiletrabajos.cl": "Chiletrabajos",
    "computrabajo.cl": "Computrabajo",
    "contutalento.cl": "Con Tu Talento",
    "bne.cl": "Bolsa Nacional de Empleo",
    "codelco.com": "Codelco Empleos",
    "finning.com": "Finning Careers",
}


def _host_key(url: str) -> str:
    host = (urlsplit(str(url or "").strip()).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _registrable_host(host: str) -> str:
    # Conservador: detecta duplicados por hostname y subdominio inmediato.
    # No intenta resolver todas las reglas de Public Suffix List.
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _search_url(template: str, query: str) -> str:
    if "{query}" in template:
        return template.replace("{query}", quote_plus(query))
    parts = urlsplit(template)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params.setdefault("q", query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def evaluate_portal_candidate(
    name: str,
    url_template: str,
    *,
    existing_portals: list[dict] | None = None,
    builtin_domains: dict[str, str] | None = None,
) -> dict:
    """Prueba una búsqueda pública real antes de permitir guardar el portal."""
    name = " ".join(str(name or "").split())
    template = str(url_template or "").strip()
    if not name:
        return {"approved": False, "reason": "Ingrese el nombre del portal."}
    if len(name) > 80 or len(template) < 8 or len(template) > 1000:
        return {"approved": False, "reason": "Revise el nombre y la longitud de la URL."}
    if template.count("{query}") > 1:
        return {"approved": False, "reason": "La URL puede contener {query} una sola vez."}

    try:
        sources._validate_public_portal_url(_search_url(template, "Analista"))
    except Exception as exc:
        return {"approved": False, "reason": str(exc)}

    host = _host_key(template)
    root = _registrable_host(host)
    builtins = builtin_domains or BUILTIN_PORTAL_DOMAINS
    for domain, label in builtins.items():
        if root == domain or host == domain or host.endswith("." + domain):
            return {
                "approved": False,
                "duplicate": True,
                "reason": f"Este dominio ya corresponde al portal integrado «{label}». No lo agregue nuevamente.",
            }

    for portal in existing_portals or []:
        existing_host = _host_key(portal.get("url_template", ""))
        if existing_host and (
            existing_host == host
            or _registrable_host(existing_host) == root
            or existing_host.endswith("." + host)
            or host.endswith("." + existing_host)
        ):
            return {
                "approved": False,
                "duplicate": True,
                "existing_portal": portal.get("name", "Portal guardado"),
                "reason": f"La dirección pertenece al mismo portal que «{portal.get('name', 'Portal guardado')}». Use el registro existente en lugar de duplicarlo.",
            }

    try:
        target = _search_url(template, "Analista")
        response = sources._request_get(target, timeout=12, allow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            return {"approved": False, "reason": "La búsqueda redirige a otra página; ingrese directamente la URL de resultados."}
        if response.status_code in {401, 403, 407, 429}:
            return {"approved": False, "reason": f"El portal bloqueó la prueba (HTTP {response.status_code}). No se intentará evadir el bloqueo."}
        response.raise_for_status()
        if "html" not in str(response.headers.get("Content-Type", "text/html")).lower():
            return {"approved": False, "reason": "La URL no entrega una página HTML pública compatible."}
        html = response.text or ""
        if len(html) < 300:
            return {"approved": False, "reason": "La página devolvió muy poco contenido para comprobar una búsqueda."}
        soup = BeautifulSoup(html, "html.parser")
        page_text = " ".join(soup.stripped_strings).casefold()
        blocked_markers = (
            "captcha", "verify you are human", "access denied",
            "checking your browser", "unusual traffic", "robot check",
            "complete the security check",
        )
        if any(marker in page_text for marker in blocked_markers):
            return {"approved": False, "reason": "El portal muestra un CAPTCHA o control anti-automatización."}
        if not soup.select("a[href]"):
            return {"approved": False, "reason": "La página no expone enlaces públicos para identificar resultados."}
        job_markers = (
            "analista", "empleo", "trabajo", "vacante", "oferta laboral",
            "job", "career", "postul", "cargo", "resultados de búsqueda",
        )
        if not any(marker in page_text for marker in job_markers):
            return {"approved": False, "reason": "La página respondió, pero no hay señales de resultados de empleo para la consulta de prueba."}
        return {
            "approved": True,
            "reason": "Prueba superada: dominio público, respuesta HTTP correcta y contenido compatible con resultados de empleo.",
            "host": host,
            "test_query": "Analista",
            "http_status": int(response.status_code),
        }
    except Exception as exc:
        return {"approved": False, "reason": f"No fue posible completar la prueba de búsqueda: {type(exc).__name__}: {exc}"}


def validate_new_search_terms(
    terms: list[str],
    *,
    existing_terms: list[str] | None = None,
) -> dict:
    """Normaliza y separa términos nuevos válidos, duplicados y no admisibles."""
    known = {" ".join(str(item).split()).casefold() for item in (existing_terms or [])}
    accepted: list[str] = []
    duplicates: list[str] = []
    rejected: list[dict] = []
    for raw in terms or []:
        term = " ".join(str(raw or "").split())
        key = term.casefold()
        if len(term) < 2 or len(term) > 160:
            rejected.append({"term": term, "reason": "Debe tener entre 2 y 160 caracteres."})
            continue
        if re.search(r"https?://|www\\.|@|[<>]", term, flags=re.I):
            rejected.append({"term": term, "reason": "No parece un cargo o una función válida."})
            continue
        if key in known:
            duplicates.append(term)
            continue
        accepted.append(term)
        known.add(key)
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}
