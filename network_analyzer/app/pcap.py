
import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from scapy.layers.inet import IP, TCP
from scapy.layers.inet6 import IPv6
from scapy.utils import PcapNgReader, PcapReader


logger = logging.getLogger(__name__)


@dataclass
class FlowState:
    key: tuple
    first_timestamp: float
    last_timestamp: float

    client: tuple | None = None
    server: tuple | None = None

    syn_timestamp: float | None = None
    handshake_rtts: list[float] = field(default_factory=list)

    retransmission_count: int = 0
    zero_window_event_count: int = 0
    reset_count: int = 0

    seen_segments: deque = field(default_factory=lambda: deque(maxlen=10000))
    seen_segment_keys: set = field(default_factory=set)

    zero_window_active: dict = field(default_factory=dict)

    def remember_segment(self, signature: tuple) -> bool:
        if signature in self.seen_segment_keys:
            return True

        if len(self.seen_segments) == self.seen_segments.maxlen:
            old = self.seen_segments.popleft()
            self.seen_segment_keys.discard(old)

        self.seen_segments.append(signature)
        self.seen_segment_keys.add(signature)
        return False


def packet_timestamp(packet) -> float:
    return float(packet.time)


def ip_endpoints(packet) -> tuple[tuple[str, str], tuple[str, str]] | None:
    if IP in packet:
        return (str(packet[IP].src), str(packet[IP].dst))
    if IPv6 in packet:
        return (str(packet[IPv6].src), str(packet[IPv6].dst))
    return None


def tcp_flow_key(packet) -> tuple | None:
    if TCP not in packet:
        return None

    endpoints = ip_endpoints(packet)
    if endpoints is None:
        return None

    src, dst = endpoints
    sport, dport = int(packet[TCP].sport), int(packet[TCP].dport)

    left = (src, sport)
    right = (dst, dport)

    return (left, right) if left <= right else (right, left)


def tcp_payload_bytes(packet) -> bytes:
    if TCP not in packet:
        return b""
    payload = bytes(packet[TCP].payload)
    return payload


def tcp_payload_len(packet) -> int:
    return len(tcp_payload_bytes(packet))


def captured_packet_length(packet) -> int:
    wirelen = getattr(packet, "wirelen", None)
    if wirelen:
        return int(wirelen)
    return len(bytes(packet))


def iter_packets(path: Path) -> Iterator:
    reader_cls = PcapNgReader if path.suffix.lower() == ".pcapng" else PcapReader

    logger.debug("Opening pcap file %s with %s", path, reader_cls.__name__)

    reader = reader_cls(str(path))
    try:
        for packet in reader:
            yield packet
    finally:
        close = getattr(reader, "close", None)
        if close is not None:
            close()
        logger.debug("Closed pcap file %s", path)