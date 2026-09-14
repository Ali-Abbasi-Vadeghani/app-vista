
from app.models import AppReview, AppStats, NetworkMeasurement


def test_app_stats_columns():
    columns = {c.name for c in AppStats.__table__.columns}
    expected = {
        "id",
        "application_id",
        "package_name",
        "crawl_timestamp",
        "min_installs",
        "score",
        "ratings",
        "reviews",
        "updated",
        "version",
        "ad_supported",
        "created_at",
    }
    assert expected.issubset(columns)


def test_app_review_columns():
    columns = {c.name for c in AppReview.__table__.columns}
    expected = {
        "id",
        "application_id",
        "package_name",
        "review_id",
        "review_at",
        "user_name",
        "thumbs_up_count",
        "score",
        "content",
        "crawl_timestamp",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(columns)


def test_network_measurement_columns():
    columns = {c.name for c in NetworkMeasurement.__table__.columns}
    expected = {
        "id",
        "application_id",
        "package_name",
        "scenario",
        "pcap_filename",
        "pcap_sha256",
        "captured_at",
        "packet_count",
        "tcp_packet_count",
        "tcp_flow_count",
        "handshake_rtt_ms",
        "retransmission_count",
        "zero_window_event_count",
        "tcp_reset_drops",
        "total_transferred_bytes",
        "total_payload_bytes",
        "overhead_ratio",
        "created_at",
    }
    assert expected.issubset(columns)