
from pathlib import Path

import pytest
from scapy.all import IP, TCP, Raw, wrpcap

from app.pcap import (
    captured_packet_length,
    ip_endpoints,
    iter_packets,
    packet_timestamp,
    tcp_flow_key,
    tcp_payload_bytes,
    tcp_payload_len,
)


def test_ip_endpoints_ipv4(build_packet):
    pkt = build_packet(src="1.2.3.4", dst="5.6.7.8")
    assert ip_endpoints(pkt) == ("1.2.3.4", "5.6.7.8")


def test_ip_endpoints_non_ip():
    from scapy.layers.l2 import Ether
    pkt = Ether()
    assert ip_endpoints(pkt) is None


def test_tcp_flow_key_symmetric(build_packet):
    pkt_a = build_packet(src="10.0.0.1", dst="10.0.0.2", sport=1234, dport=80)
    pkt_b = build_packet(src="10.0.0.2", dst="10.0.0.1", sport=80, dport=1234)

    assert tcp_flow_key(pkt_a) == tcp_flow_key(pkt_b)


def test_tcp_flow_key_different_flows(build_packet):
    pkt_a = build_packet(src="10.0.0.1", dst="10.0.0.2", sport=1234, dport=80)
    pkt_b = build_packet(src="10.0.0.1", dst="10.0.0.2", sport=1234, dport=443)

    assert tcp_flow_key(pkt_a) != tcp_flow_key(pkt_b)


def test_tcp_flow_key_non_tcp():
    from scapy.layers.inet import IP, UDP
    pkt = IP(src="1.1.1.1", dst="2.2.2.2") / UDP(sport=1, dport=2)
    assert tcp_flow_key(pkt) is None


def test_tcp_payload_bytes_and_len(build_packet):
    pkt = build_packet(payload=b"abcdef")
    assert tcp_payload_bytes(pkt) == b"abcdef"
    assert tcp_payload_len(pkt) == 6


def test_tcp_payload_empty(build_packet):
    pkt = build_packet()
    assert tcp_payload_bytes(pkt) == b""
    assert tcp_payload_len(pkt) == 0


def test_packet_timestamp(build_packet):
    pkt = build_packet(timestamp=1234.5)
    assert packet_timestamp(pkt) == pytest.approx(1234.5)


def test_captured_packet_length(build_packet):
    pkt = build_packet(payload=b"12345")
    length = captured_packet_length(pkt)
    assert length >= len(b"12345")


def test_iter_packets_reads_all(tmp_path: Path, build_packet):
    packets = [build_packet(timestamp=1.0), build_packet(timestamp=2.0)]
    path = tmp_path / "two.pcap"
    wrpcap(str(path), packets)

    read = list(iter_packets(path))
    assert len(read) == 2


def test_iter_packets_pcapng(tmp_path: Path, build_packet):
    packets = [build_packet(timestamp=1.0)]
    path = tmp_path / "single.pcapng"
    wrpcap(str(path), packets)

    read = list(iter_packets(path))
    assert len(read) == 1