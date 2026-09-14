
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as analyzer_main


@pytest.fixture
def client():
    return TestClient(analyzer_main.app)


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "network-analyzer"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_rejects_bad_scenario(client, handshake_pcap: Path, monkeypatch):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 1
    )

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "invalid"},
        )

    assert response.status_code == 400


def test_analyze_rejects_bad_extension(client, handshake_pcap: Path, monkeypatch):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 1
    )

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.txt", fh, "text/plain")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 400


def test_analyze_rejects_disallowed_package(client, handshake_pcap: Path, monkeypatch):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", {"com.allowed"})

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.other", "scenario": "upload"},
        )

    assert response.status_code == 400


def test_analyze_package_not_found(client, handshake_pcap: Path, monkeypatch):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: None
    )

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 404


def test_analyze_success(client, handshake_pcap: Path, monkeypatch):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 42
    )
    monkeypatch.setattr(
        analyzer_main,
        "publish_network_measurement",
        lambda metrics: "test-message-id",
    )

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["message_id"] == "test-message-id"
    assert body["metrics"]["application_id"] == 42
    assert body["metrics"]["package_name"] == "com.test"
    assert body["metrics"]["scenario"] == "upload"


def test_analyze_redis_failure_returns_503(
    client, handshake_pcap: Path, monkeypatch
):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 1
    )

    def fail(_):
        raise RuntimeError("redis down")

    monkeypatch.setattr(analyzer_main, "publish_network_measurement", fail)

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 503


def test_analyze_api_unavailable_returns_503(
    client, handshake_pcap: Path, monkeypatch
):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())

    def fail(_):
        raise RuntimeError("api down")

    monkeypatch.setattr(analyzer_main, "get_application_id", fail)

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 503


def test_analyze_too_large_file(
    client, handshake_pcap: Path, monkeypatch
):
    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(analyzer_main, "MAX_PCAP_BYTES", 10)
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 1
    )

    with handshake_pcap.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("test.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 413


def test_analyze_empty_pcap(
    client, tmp_path: Path, monkeypatch
):
    from scapy.utils import PcapWriter
    empty = tmp_path / "empty.pcap"
    writer = PcapWriter(str(empty), sync=True)
    writer.close()

    monkeypatch.setattr(analyzer_main, "ALLOWED_PACKAGES", set())
    monkeypatch.setattr(
        analyzer_main, "get_application_id", lambda pkg: 1
    )
    monkeypatch.setattr(
        analyzer_main,
        "publish_network_measurement",
        lambda metrics: "id",
    )

    with empty.open("rb") as fh:
        response = client.post(
            "/analyze",
            files={"file": ("empty.pcap", fh, "application/octet-stream")},
            data={"package_name": "com.test", "scenario": "upload"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["packet_count"] == 0