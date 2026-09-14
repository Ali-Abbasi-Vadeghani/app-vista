
import struct
from pathlib import Path

import pytest
from scapy.all import IP, TCP, Raw, wrpcap


def _make_tcp_packet(
    src="10.0.0.1",
    dst="10.0.0.2",
    sport=12345,
    dport=80,
    seq=0,
    ack=0,
    flags="S",
    window=65535,
    payload=b"",
    timestamp=0.0,
):
    pkt = (
        IP(src=src, dst=dst)
        / TCP(sport=sport, dport=dport, seq=seq, ack=ack, flags=flags, window=window)
    )
    if payload:
        pkt = pkt / Raw(load=payload)
    pkt.time = timestamp
    return pkt


@pytest.fixture
def build_packet():
    return _make_tcp_packet


@pytest.fixture
def handshake_pcap(tmp_path: Path):
    packets = [
        _make_tcp_packet(flags="S", seq=1000, timestamp=1.000),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="SA",
            seq=5000,
            ack=1001,
            timestamp=1.050,
        ),
        _make_tcp_packet(
            flags="A",
            seq=1001,
            ack=5001,
            timestamp=1.051,
        ),
    ]
    path = tmp_path / "handshake.pcap"
    wrpcap(str(path), packets)
    return path


@pytest.fixture
def payload_pcap(tmp_path: Path):
    packets = [
        _make_tcp_packet(flags="S", seq=1000, timestamp=1.000),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="SA",
            seq=5000,
            ack=1001,
            timestamp=1.020,
        ),
        _make_tcp_packet(flags="A", seq=1001, ack=5001, timestamp=1.021),
        _make_tcp_packet(
            flags="PA",
            seq=1001,
            ack=5001,
            payload=b"hello world",
            timestamp=1.030,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="PA",
            seq=5001,
            ack=1012,
            payload=b"response data",
            timestamp=1.040,
        ),
    ]
    path = tmp_path / "payload.pcap"
    wrpcap(str(path), packets)
    return path


@pytest.fixture
def retransmission_pcap(tmp_path: Path):
    payload = b"duplicate me"
    packets = [
        _make_tcp_packet(flags="S", seq=1000, timestamp=1.000),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="SA",
            seq=5000,
            ack=1001,
            timestamp=1.010,
        ),
        _make_tcp_packet(
            flags="PA",
            seq=1001,
            ack=5001,
            payload=payload,
            timestamp=1.020,
        ),
        _make_tcp_packet(
            flags="PA",
            seq=1001,
            ack=5001,
            payload=payload,
            timestamp=1.025,
        ),
    ]
    path = tmp_path / "retrans.pcap"
    wrpcap(str(path), packets)
    return path


@pytest.fixture
def zero_window_pcap(tmp_path: Path):
    packets = [
        _make_tcp_packet(flags="S", seq=1000, timestamp=1.000),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="SA",
            seq=5000,
            ack=1001,
            timestamp=1.010,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="A",
            seq=5001,
            ack=1001,
            window=0,
            timestamp=1.020,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="A",
            seq=5001,
            ack=1001,
            window=0,
            timestamp=1.025,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="A",
            seq=5001,
            ack=1001,
            window=1024,
            timestamp=1.030,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="A",
            seq=5001,
            ack=1001,
            window=0,
            timestamp=1.035,
        ),
    ]
    path = tmp_path / "zero_window.pcap"
    wrpcap(str(path), packets)
    return path


@pytest.fixture
def rst_pcap(tmp_path: Path):
    packets = [
        _make_tcp_packet(flags="S", seq=1000, timestamp=1.000),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="SA",
            seq=5000,
            ack=1001,
            timestamp=1.010,
        ),
        _make_tcp_packet(
            src="10.0.0.2",
            dst="10.0.0.1",
            sport=80,
            dport=12345,
            flags="R",
            seq=5001,
            ack=1001,
            timestamp=1.020,
        ),
    ]
    path = tmp_path / "rst.pcap"
    wrpcap(str(path), packets)
    return path


@pytest.fixture
def multi_flow_pcap(tmp_path: Path):
    packets = [
        _make_tcp_packet(src="10.0.0.1", dst="10.0.0.2", sport=1111, dport=80,
                         flags="S", seq=100, timestamp=1.000),
        _make_tcp_packet(src="10.0.0.2", dst="10.0.0.1", sport=80, dport=1111,
                         flags="SA", seq=200, ack=101, timestamp=1.010),
        _make_tcp_packet(src="10.0.0.1", dst="10.0.0.3", sport=2222, dport=443,
                         flags="S", seq=300, timestamp=1.100),
        _make_tcp_packet(src="10.0.0.3", dst="10.0.0.1", sport=443, dport=2222,
                         flags="SA", seq=400, ack=301, timestamp=1.150),
    ]
    path = tmp_path / "multi_flow.pcap"
    wrpcap(str(path), packets)
    return path