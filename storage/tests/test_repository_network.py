
import pytest

from app.models import NetworkMeasurement
from app.repository import (
    save_network_measurement,
    save_network_measurement_no_commit,
)


def test_save_network_measurement_inserts(db_session, network_payload):
    m = save_network_measurement(db_session, network_payload)

    assert m.id is not None
    assert m.application_id == 1
    assert m.package_name == "com.test.app"
    assert m.scenario == "upload"
    assert m.pcap_sha256 == "a" * 64
    assert m.packet_count == 100
    assert m.handshake_rtt_ms == 45.5
    assert m.overhead_ratio == 0.1


def test_save_network_measurement_updates_existing(db_session, network_payload):
    save_network_measurement(db_session, network_payload)

    updated = dict(network_payload)
    updated["packet_count"] = 200
    updated["handshake_rtt_ms"] = 12.5

    save_network_measurement(db_session, updated)

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 1
    assert rows[0].packet_count == 200
    assert rows[0].handshake_rtt_ms == 12.5


def test_save_network_measurement_different_sha(db_session, network_payload):
    save_network_measurement(db_session, network_payload)

    second = dict(network_payload)
    second["pcap_sha256"] = "b" * 64
    save_network_measurement(db_session, second)

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 2


def test_save_network_measurement_different_scenario(db_session, network_payload):
    save_network_measurement(db_session, network_payload)

    second = dict(network_payload)
    second["scenario"] = "download"
    save_network_measurement(db_session, second)

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 2


def test_save_network_measurement_no_commit_stages_only(
    db_session, network_payload
):
    save_network_measurement_no_commit(db_session, network_payload)
    db_session.commit()

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 1


def test_save_network_measurement_no_commit_rollback(
    db_session, network_payload
):
    save_network_measurement_no_commit(db_session, network_payload)
    db_session.rollback()

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 0


def test_save_network_measurement_no_commit_update_existing(
    db_session, network_payload
):
    save_network_measurement(db_session, network_payload)

    updated = dict(network_payload)
    updated["packet_count"] = 999
    save_network_measurement_no_commit(db_session, updated)
    db_session.commit()

    rows = db_session.query(NetworkMeasurement).all()
    assert len(rows) == 1
    assert rows[0].packet_count == 999