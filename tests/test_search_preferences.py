from types import SimpleNamespace

import pytest

from src.db.search_preferences import save_search_portal, save_search_terms


class Query:
    def __init__(self, client, table):
        self.client, self.table_name = client, table
        self.filters, self.operation, self.payload = {}, "select", None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, *_args):
        return self

    def order(self, *_args):
        return self

    def execute(self):
        rows = self.client.rows.setdefault(self.table_name, [])
        if self.operation == "insert":
            payload = self.payload if isinstance(self.payload, list) else [self.payload]
            created = []
            for row in payload:
                item = {"id": str(len(rows) + 1), **row}
                rows.append(item)
                created.append(item)
            return SimpleNamespace(data=created)
        selected = [row for row in rows if all(row.get(k) == v for k, v in self.filters.items())]
        return SimpleNamespace(data=selected)


class Client:
    def __init__(self):
        self.rows = {}

    def table(self, name):
        return Query(self, name)


def test_custom_portal_is_saved_and_duplicate_url_reuses_existing_row():
    client = Client()
    first = save_search_portal(
        client, user_id="u1", name="Portal minero",
        url_template="https://example.cl/jobs?q={query}",
    )
    second = save_search_portal(
        client, user_id="u1", name="Otro nombre",
        url_template="https://example.cl/jobs?q={query}",
    )
    assert first["id"] == second["id"]
    assert len(client.rows["user_search_portals"]) == 1


def test_search_terms_are_saved_per_user_and_deduplicated_case_insensitively():
    client = Client()
    saved = save_search_terms(
        client, user_id="u1", term_type="funcion",
        terms=["  Gestión de proyectos TI ", "gestión de proyectos ti", "Levantamiento de requisitos"],
    )
    assert saved == ["Gestión de proyectos TI", "Levantamiento de requisitos"]
    assert len(client.rows["user_search_terms"]) == 2
    assert client.rows["user_search_terms"][0]["user_id"] == "u1"


def test_search_terms_reject_unknown_type():
    with pytest.raises(ValueError, match="Tipo de término"):
        save_search_terms(Client(), user_id="u1", term_type="empresa", terms=["x"])


def test_custom_portal_rejects_non_http_urls():
    with pytest.raises(ValueError, match="http:// o https://"):
        save_search_portal(
            Client(), user_id="u1", name="Portal",
            url_template="file:///etc/passwd",
        )



def test_custom_portal_rejects_second_url_for_same_domain():
    client = Client()
    save_search_portal(
        client, user_id="u1", name="Portal principal",
        url_template="https://jobs.example.cl/search?q={query}",
    )
    with pytest.raises(ValueError, match="mismo portal"):
        save_search_portal(
            client, user_id="u1", name="Otra sección",
            url_template="https://www.jobs.example.cl/careers",
        )
