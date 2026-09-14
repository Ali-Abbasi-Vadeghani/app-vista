
import pytest
from pydantic import ValidationError

from app import api_client


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        return self._response


def _make_client_factory(response):
    def factory(*args, **kwargs):
        return FakeClient(response)
    return factory


def test_fetch_active_applications(monkeypatch):
    payload = [
        {
            "id": 1,
            "name": "Test",
            "package_name": "com.test",
            "category": "chat",
            "is_active": True,
        }
    ]
    monkeypatch.setattr(
        api_client.httpx, "Client", _make_client_factory(FakeResponse(payload))
    )

    apps = api_client.fetch_active_applications()
    assert len(apps) == 1
    assert apps[0].id == 1
    assert apps[0].package_name == "com.test"


def test_fetch_active_applications_empty(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "Client", _make_client_factory(FakeResponse([]))
    )

    apps = api_client.fetch_active_applications()
    assert apps == []


def test_fetch_active_applications_bad_payload(monkeypatch):
    payload = [{"id": "not-an-int"}]
    monkeypatch.setattr(
        api_client.httpx, "Client", _make_client_factory(FakeResponse(payload))
    )

    with pytest.raises(ValidationError):
        api_client.fetch_active_applications()


def test_get_application_id_found(monkeypatch):
    payload = [
        {
            "id": 7,
            "name": "Test",
            "package_name": "com.test",
            "category": "chat",
            "is_active": True,
        }
    ]
    monkeypatch.setattr(
        api_client.httpx, "Client", _make_client_factory(FakeResponse(payload))
    )

    assert api_client.get_application_id("com.test") == 7


def test_get_application_id_not_found(monkeypatch):
    monkeypatch.setattr(
        api_client.httpx, "Client", _make_client_factory(FakeResponse([]))
    )

    assert api_client.get_application_id("com.missing") is None