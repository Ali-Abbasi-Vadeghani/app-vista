
import os

os.environ.setdefault("PG_HOST", "postgres")
os.environ.setdefault("PG_PORT", "5432")
os.environ.setdefault("PG_USER", "appvista")
os.environ.setdefault("PG_PASSWORD", "appvista123")
os.environ.setdefault("APP_DB", "appvista_db")
os.environ.setdefault("METABASE_DB", "metabase_db")
os.environ.setdefault("MB_URL", "http://metabase:3000")
os.environ.setdefault("MB_ADMIN_EMAIL", "admin@appvista.local")
os.environ.setdefault("MB_ADMIN_PASSWORD", "AppVista-Str0ng-2026!")

import pytest
from unittest.mock import MagicMock


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.ok = 200 <= status_code < 400

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"HTTP {self.status_code}")


@pytest.fixture
def make_response():
    def _make(status_code=200, payload=None, text=""):
        return FakeResponse(status_code, payload, text)
    return _make


@pytest.fixture
def metabase_client(monkeypatch):
    from app.metabase_client import MetabaseClient

    client = MetabaseClient(base_url="http://fake-metabase:3000")
    client.session_id = "fake-session-token"
    return client