
import hashlib
from pathlib import Path

from app.analyzer import (
    is_rst,
    is_syn,
    is_syn_ack,
    segment_signature,
    sha256_file,
)
from scapy.all import IP, TCP


def test_is_syn_true(build_packet):
    pkt = build_packet(flags="S")
    assert is_syn(pkt[TCP]) is True


def test_is_syn_false_when_ack(build_packet):
    pkt = build_packet(flags="SA")
    assert is_syn(pkt[TCP]) is False


def test_is_syn_ack_true(build_packet):
    pkt = build_packet(flags="SA")
    assert is_syn_ack(pkt[TCP]) is True


def test_is_syn_ack_false(build_packet):
    pkt = build_packet(flags="S")
    assert is_syn_ack(pkt[TCP]) is False


def test_is_rst_true(build_packet):
    pkt = build_packet(flags="R")
    assert is_rst(pkt[TCP]) is True


def test_is_rst_false(build_packet):
    pkt = build_packet(flags="A")
    assert is_rst(pkt[TCP]) is False


def test_segment_signature_none_without_payload(build_packet):
    pkt = build_packet(flags="A")
    assert segment_signature(pkt) is None


def test_segment_signature_with_payload(build_packet):
    pkt = build_packet(flags="PA", payload=b"data")
    sig = segment_signature(pkt)
    assert sig is not None
    assert isinstance(sig, tuple)
    assert len(sig) == 6


def test_segment_signature_same_payload_same_hash(build_packet):
    pkt1 = build_packet(flags="PA", seq=100, payload=b"same")
    pkt2 = build_packet(flags="PA", seq=100, payload=b"same")
    assert segment_signature(pkt1) == segment_signature(pkt2)


def test_segment_signature_different_payload(build_packet):
    pkt1 = build_packet(flags="PA", seq=100, payload=b"aaa")
    pkt2 = build_packet(flags="PA", seq=100, payload=b"bbb")
    assert segment_signature(pkt1) != segment_signature(pkt2)


def test_sha256_file(tmp_path: Path):
    path = tmp_path / "sample.bin"
    content = b"hello world"
    path.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert sha256_file(path) == expected


def test_sha256_file_large(tmp_path: Path):
    path = tmp_path / "large.bin"
    content = b"a" * (3 * 1024 * 1024)
    path.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert sha256_file(path) == expected