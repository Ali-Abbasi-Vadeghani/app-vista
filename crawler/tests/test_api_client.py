
from unittest.mock import patch

import httpx
import pytest

from app import api_client


def _fake_response(payload, status_code=200):
    request = httpx.Request("GET", "http://api:8000/applications")
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=request,
    )


@patch("app.api_client.httpx.Client.get")
def test_fetch_active_applications_uses_active_param(get_mock):
    get_mock.return_value = _fake_response(
        [
            {
                "id": 1,
                "name": "Telegram",
                "package_name": "org.telegram.messenger",
                "category": "Social",
                "is_active": True,
            }
        ]
    )

    apps = api_client.fetch_active_applications()

    assert len(apps) == 1
    assert apps[0].package_name == "org.telegram.messenger"

    _, kwargs = get_mock.call_args
    assert kwargs["params"] == {"active": "true"}


@patch("app.api_client.httpx.Client.get")
def test_fetch_active_applications_raises_on_http_error(get_mock):
    get_mock.return_value = _fake_response([], status_code=500)

    with pytest.raises(httpx.HTTPStatusError):
        api_client.fetch_active_applications()


@patch("app.api_client.httpx.Client.get")
def test_fetch_active_applications_empty(get_mock):
    get_mock.return_value = _fake_response([])

    assert api_client.fetch_active_applications() == []


@patch("app.api_client.httpx.Client.get")
def test_fetch_active_applications_ignores_extra_fields(get_mock):
    get_mock.return_value = _fake_response(
        [
            {
                "id": 1,
                "name": "Telegram",
                "package_name": "org.telegram.messenger",
                "category": "Social",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ]
    )

    apps = api_client.fetch_active_applications()
    assert len(apps) == 1