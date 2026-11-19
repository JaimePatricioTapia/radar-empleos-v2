from src.search.ingestion import _parse_published_at, _stable_hash
from src.search.sources import normalize_offer


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
