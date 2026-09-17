
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppReview, AppStats, NetworkMeasurement


logger = logging.getLogger(__name__)


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        logger.warning("Failed to parse datetime value=%r", value)
        return None



def save_network_measurement(db: Session, payload: dict) -> NetworkMeasurement:
    existing = db.scalar(
        select(NetworkMeasurement).where(
            NetworkMeasurement.application_id == payload["application_id"],
            NetworkMeasurement.scenario == payload["scenario"],
            NetworkMeasurement.pcap_sha256 == payload["pcap_sha256"],
        )
    )

    captured_at = _parse_datetime(payload.get("captured_at"))

    if existing is not None:
        existing.pcap_filename = payload.get("pcap_filename")
        existing.captured_at = captured_at
        existing.packet_count = payload.get("packet_count", 0)
        existing.tcp_packet_count = payload.get("tcp_packet_count", 0)
        existing.tcp_flow_count = payload.get("tcp_flow_count", 0)
        existing.handshake_rtt_ms = payload.get("handshake_rtt_ms")
        existing.retransmission_count = payload.get("retransmission_count", 0)
        existing.zero_window_event_count = payload.get("zero_window_event_count", 0)
        existing.tcp_reset_drops = payload.get("tcp_reset_drops", 0)
        existing.total_transferred_bytes = payload.get("total_transferred_bytes", 0)
        existing.total_payload_bytes = payload.get("total_payload_bytes", 0)
        existing.overhead_ratio = payload.get("overhead_ratio")

        db.commit()
        db.refresh(existing)

        logger.info(
            "Updated network_measurement package=%s scenario=%s sha=%s",
            existing.package_name,
            existing.scenario,
            existing.pcap_sha256[:8],
        )

        return existing

    measurement = NetworkMeasurement(
        application_id=payload["application_id"],
        package_name=payload["package_name"],
        scenario=payload["scenario"],
        pcap_filename=payload.get("pcap_filename"),
        pcap_sha256=payload["pcap_sha256"],
        captured_at=captured_at,
        packet_count=payload.get("packet_count", 0),
        tcp_packet_count=payload.get("tcp_packet_count", 0),
        tcp_flow_count=payload.get("tcp_flow_count", 0),
        handshake_rtt_ms=payload.get("handshake_rtt_ms"),
        retransmission_count=payload.get("retransmission_count", 0),
        zero_window_event_count=payload.get("zero_window_event_count", 0),
        tcp_reset_drops=payload.get("tcp_reset_drops", 0),
        total_transferred_bytes=payload.get("total_transferred_bytes", 0),
        total_payload_bytes=payload.get("total_payload_bytes", 0),
        overhead_ratio=payload.get("overhead_ratio"),
    )

    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    logger.info(
        "Inserted network_measurement package=%s scenario=%s sha=%s",
        measurement.package_name,
        measurement.scenario,
        measurement.pcap_sha256[:8],
    )

    return measurement


def save_network_measurement_no_commit(db: Session, payload: dict) -> None:
    existing = db.scalar(
        select(NetworkMeasurement).where(
            NetworkMeasurement.application_id == payload["application_id"],
            NetworkMeasurement.scenario == payload["scenario"],
            NetworkMeasurement.pcap_sha256 == payload["pcap_sha256"],
        )
    )

    captured_at = _parse_datetime(payload.get("captured_at"))

    if existing is not None:
        existing.pcap_filename = payload.get("pcap_filename")
        existing.captured_at = captured_at
        existing.packet_count = payload.get("packet_count", 0)
        existing.tcp_packet_count = payload.get("tcp_packet_count", 0)
        existing.tcp_flow_count = payload.get("tcp_flow_count", 0)
        existing.handshake_rtt_ms = payload.get("handshake_rtt_ms")
        existing.retransmission_count = payload.get("retransmission_count", 0)
        existing.zero_window_event_count = payload.get("zero_window_event_count", 0)
        existing.tcp_reset_drops = payload.get("tcp_reset_drops", 0)
        existing.total_transferred_bytes = payload.get("total_transferred_bytes", 0)
        existing.total_payload_bytes = payload.get("total_payload_bytes", 0)
        existing.overhead_ratio = payload.get("overhead_ratio")

        logger.debug(
            "Staged update network_measurement package=%s scenario=%s",
            existing.package_name,
            existing.scenario,
        )
        return

    measurement = NetworkMeasurement(
        application_id=payload["application_id"],
        package_name=payload["package_name"],
        scenario=payload["scenario"],
        pcap_filename=payload.get("pcap_filename"),
        pcap_sha256=payload["pcap_sha256"],
        captured_at=captured_at,
        packet_count=payload.get("packet_count", 0),
        tcp_packet_count=payload.get("tcp_packet_count", 0),
        tcp_flow_count=payload.get("tcp_flow_count", 0),
        handshake_rtt_ms=payload.get("handshake_rtt_ms"),
        retransmission_count=payload.get("retransmission_count", 0),
        zero_window_event_count=payload.get("zero_window_event_count", 0),
        tcp_reset_drops=payload.get("tcp_reset_drops", 0),
        total_transferred_bytes=payload.get("total_transferred_bytes", 0),
        total_payload_bytes=payload.get("total_payload_bytes", 0),
        overhead_ratio=payload.get("overhead_ratio"),
    )
    db.add(measurement)

    logger.debug(
        "Staged insert network_measurement package=%s scenario=%s",
        measurement.package_name,
        measurement.scenario,
    )