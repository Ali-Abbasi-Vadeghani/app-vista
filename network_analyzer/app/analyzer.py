
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from scapy.layers.inet import TCP

from .pcap import (
    FlowState,
    captured_packet_length,
    ip_endpoints,
    iter_packets,
    packet_timestamp,
    tcp_flow_key,
    tcp_payload_bytes,
    tcp_payload_len,
)


logger = logging.getLogger(__name__)


SYN = 0x02
ACK = 0x10
RST = 0x04


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def is_syn(tcp: TCP) -> bool:
    return bool(int(tcp.flags) & SYN) and not bool(int(tcp.flags) & ACK)


def is_syn_ack(tcp: TCP) -> bool:
    return bool(int(tcp.flags) & SYN) and bool(int(tcp.flags) & ACK)


def is_rst(tcp: TCP) -> bool:
    return bool(int(tcp.flags) & RST)


def segment_signature(packet) -> tuple | None:
    if TCP not in packet:
        return None

    endpoints = ip_endpoints(packet)
    if endpoints is None:
        return None

    payload = tcp_payload_bytes(packet)
    if not payload:
        return None

    tcp = packet[TCP]
    payload_hash = hashlib.sha256(payload).hexdigest()

    return (
        endpoints[0],
        endpoints[1],
        int(tcp.sport),
        int(tcp.dport),
        int(tcp.seq),
        payload_hash,
    )


def analyze_pcap(
    path: Path,
    application_id: int,
    package_name: str,
    scenario: str,
    pcap_filename: str | None = None,
) -> dict:
    logger.info(
        "Starting pcap analysis package=%s scenario=%s file=%s",
        package_name,
        scenario,
        pcap_filename or path.name,
    )

    flows: dict[tuple, FlowState] = {}

    packet_count = 0
    tcp_packet_count = 0
    total_transferred_bytes = 0
    total_payload_bytes = 0
    first_timestamp: float | None = None

    for packet in iter_packets(path):
        packet_count += 1

        timestamp = packet_timestamp(packet)
        if first_timestamp is None:
            first_timestamp = timestamp

        total_transferred_bytes += captured_packet_length(packet)

        if TCP not in packet:
            continue

        tcp_packet_count += 1
        total_payload_bytes += tcp_payload_len(packet)

        flow_key = tcp_flow_key(packet)
        if flow_key is None:
            continue

        flow = flows.get(flow_key)
        if flow is None:
            flow = FlowState(
                key=flow_key,
                first_timestamp=timestamp,
                last_timestamp=timestamp,
            )
            flows[flow_key] = flow
        else:
            flow.last_timestamp = timestamp

        endpoints = ip_endpoints(packet)
        if endpoints is None:
            continue

        src_endpoint = (endpoints[0], int(packet[TCP].sport))
        dst_endpoint = (endpoints[1], int(packet[TCP].dport))

        if is_syn(packet[TCP]) and flow.syn_timestamp is None:
            flow.syn_timestamp = timestamp
            flow.client = src_endpoint
            flow.server = dst_endpoint

        elif (
            is_syn_ack(packet[TCP])
            and flow.syn_timestamp is not None
            and flow.server == src_endpoint
            and flow.client == dst_endpoint
            and timestamp >= flow.syn_timestamp
        ):
            flow.handshake_rtts.append(timestamp - flow.syn_timestamp)
            flow.syn_timestamp = None

        if is_rst(packet[TCP]):
            flow.reset_count += 1

        direction = src_endpoint
        window = int(packet[TCP].window)
        previous_zero = flow.zero_window_active.get(direction, False)

        if window == 0 and not previous_zero:
            flow.zero_window_event_count += 1
            flow.zero_window_active[direction] = True
        elif window > 0:
            flow.zero_window_active[direction] = False

        signature = segment_signature(packet)
        if signature is not None and flow.remember_segment(signature):
            flow.retransmission_count += 1

    handshake_rtts: list[float] = []
    for flow in flows.values():
        handshake_rtts.extend(flow.handshake_rtts)

    retransmission_count = sum(
        flow.retransmission_count for flow in flows.values()
    )
    zero_window_event_count = sum(
        flow.zero_window_event_count for flow in flows.values()
    )
    tcp_reset_drops = sum(flow.reset_count for flow in flows.values())

    handshake_rtt_ms = (
        sum(handshake_rtts) / len(handshake_rtts) * 1000.0
        if handshake_rtts
        else None
    )

    overhead_bytes = max(
        total_transferred_bytes - total_payload_bytes,
        0,
    )

    overhead_ratio = (
        overhead_bytes / total_transferred_bytes
        if total_transferred_bytes > 0
        else None
    )

    captured_at = (
        datetime.fromtimestamp(first_timestamp, tz=timezone.utc)
        if first_timestamp is not None
        else None
    )

    result = {
        "application_id": application_id,
        "package_name": package_name,
        "scenario": scenario,
        "pcap_filename": pcap_filename or path.name,
        "pcap_sha256": sha256_file(path),
        "captured_at": captured_at,
        "packet_count": packet_count,
        "tcp_packet_count": tcp_packet_count,
        "tcp_flow_count": len(flows),
        "handshake_rtt_ms": handshake_rtt_ms,
        "retransmission_count": retransmission_count,
        "zero_window_event_count": zero_window_event_count,
        "tcp_reset_drops": tcp_reset_drops,
        "total_transferred_bytes": total_transferred_bytes,
        "total_payload_bytes": total_payload_bytes,
        "overhead_ratio": overhead_ratio,
    }

    logger.info(
        "Pcap analysis finished package=%s scenario=%s packets=%s flows=%s "
        "retransmissions=%s zero_window=%s rst=%s",
        package_name,
        scenario,
        packet_count,
        len(flows),
        retransmission_count,
        zero_window_event_count,
        tcp_reset_drops,
    )

    return result