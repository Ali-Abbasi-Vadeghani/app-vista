
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import Column, Integer, String, Table

from app.database import Base, SessionLocal, engine


if "applications" not in Base.metadata.tables:
    Table(
        "applications",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(255)),
        Column("package_name", String(255)),
        Column("category", String(100)),
    )


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def stats_payload():
    return {
        "message_id": str(uuid.uuid4()),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "application_id": 1,
        "package_name": "com.test.app",
        "crawl_timestamp": "2024-06-01T12:00:00+00:00",
        "data": {
            "minInstalls": 1000,
            "score": 4.5,
            "ratings": 200,
            "reviews": 50,
            "updated": "2024-05-20",
            "version": "1.2.3",
            "adSupported": True,
        },
    }


@pytest.fixture
def review_payload():
    return {
        "message_id": str(uuid.uuid4()),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "application_id": 1,
        "package_name": "com.test.app",
        "crawl_timestamp": "2024-06-01T12:00:00+00:00",
        "data": {
            "reviewId": "rev-001",
            "at": "2024-05-30T10:00:00+00:00",
            "userName": "alice",
            "thumbsUpCount": 5,
            "score": 5,
            "content": "great app",
        },
    }


@pytest.fixture
def network_payload():
    return {
        "message_id": str(uuid.uuid4()),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "application_id": 1,
        "package_name": "com.test.app",
        "scenario": "upload",
        "pcap_filename": "test.pcap",
        "pcap_sha256": "a" * 64,
        "captured_at": "2024-06-01T11:00:00+00:00",
        "packet_count": 100,
        "tcp_packet_count": 95,
        "tcp_flow_count": 3,
        "handshake_rtt_ms": 45.5,
        "retransmission_count": 2,
        "zero_window_event_count": 1,
        "tcp_reset_drops": 0,
        "total_transferred_bytes": 50000,
        "total_payload_bytes": 45000,
        "overhead_ratio": 0.1,
    }