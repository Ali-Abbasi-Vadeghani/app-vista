
from pathlib import Path

import pytest

from app.analyzer import analyze_pcap


PKG = "com.example.app"
APP_ID = 42


def test_analyze_handshake_rtt(handshake_pcap: Path):
    result = analyze_pcap(
        path=handshake_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["application_id"] == APP_ID
    assert result["package_name"] == PKG
    assert result["scenario"] == "upload"
    assert result["packet_count"] == 3
    assert result["tcp_packet_count"] == 3
    assert result["tcp_flow_count"] == 1

    assert result["handshake_rtt_ms"] == pytest.approx(50.0, abs=1.0)


def test_analyze_payload_counts(payload_pcap: Path):
    result = analyze_pcap(
        path=payload_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="download",
    )

    assert result["total_payload_bytes"] == 24
    assert result["total_transferred_bytes"] > 24
    assert result["overhead_ratio"] is not None
    assert 0.0 <= result["overhead_ratio"] < 1.0


def test_analyze_retransmission_detected(retransmission_pcap: Path):
    result = analyze_pcap(
        path=retransmission_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["retransmission_count"] == 1


def test_analyze_no_retransmission_in_clean_capture(payload_pcap: Path):
    result = analyze_pcap(
        path=payload_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["retransmission_count"] == 0


def test_analyze_zero_window(zero_window_pcap: Path):
    result = analyze_pcap(
        path=zero_window_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="download",
    )

    assert result["zero_window_event_count"] == 2


def test_analyze_rst_drops(rst_pcap: Path):
    result = analyze_pcap(
        path=rst_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="download",
    )

    assert result["tcp_reset_drops"] == 1


def test_analyze_multi_flow(multi_flow_pcap: Path):
    result = analyze_pcap(
        path=multi_flow_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["tcp_flow_count"] == 2
    assert result["handshake_rtt_ms"] is not None


def test_analyze_captured_at_set(handshake_pcap: Path):
    result = analyze_pcap(
        path=handshake_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["captured_at"] is not None


def test_analyze_pcap_sha256(handshake_pcap: Path):
    result = analyze_pcap(
        path=handshake_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert isinstance(result["pcap_sha256"], str)
    assert len(result["pcap_sha256"]) == 64


def test_analyze_pcap_filename_override(handshake_pcap: Path):
    result = analyze_pcap(
        path=handshake_pcap,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
        pcap_filename="custom.pcap",
    )

    assert result["pcap_filename"] == "custom.pcap"


def test_analyze_empty_capture(tmp_path: Path):
    empty = tmp_path / "empty.pcap"
    empty.write_bytes(b"")

    from scapy.utils import PcapWriter
    writer = PcapWriter(str(empty), sync=True)
    writer.close()

    result = analyze_pcap(
        path=empty,
        application_id=APP_ID,
        package_name=PKG,
        scenario="upload",
    )

    assert result["packet_count"] == 0
    assert result["handshake_rtt_ms"] is None
    assert result["overhead_ratio"] is None