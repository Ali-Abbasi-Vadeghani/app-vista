
import json

import pytest
import redis

from app import redis_client as rc


class FakeRedis:
    def __init__(self):
        self.data: dict[str, list[str]] = {}

    def rpush(self, queue, payload):
        self.data.setdefault(queue, []).append(payload)

    def ping(self):
        return True

    def lpop(self, queue):
        items = self.data.get(queue, [])
        if not items:
            return None
        return items.pop(0)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rc, "redis_client", fake)
    return fake


def test_publish_returns_message_id(fake_redis):
    message_id = rc.publish_network_measurement({"package_name": "x"})
    assert isinstance(message_id, str)
    assert len(message_id) > 0


def test_publish_pushes_to_queue(fake_redis):
    rc.publish_network_measurement(
        {"package_name": "x", "scenario": "upload"}
    )

    assert len(fake_redis.data[rc.NETWORK_MEASUREMENTS_QUEUE]) == 1


def test_publish_payload_contains_fields(fake_redis):
    rc.publish_network_measurement(
        {"package_name": "x", "scenario": "upload"}
    )

    raw = fake_redis.data[rc.NETWORK_MEASUREMENTS_QUEUE][0]
    payload = json.loads(raw)

    assert payload["package_name"] == "x"
    assert payload["scenario"] == "upload"
    assert "message_id" in payload
    assert "enqueued_at" in payload


def test_publish_multiple(fake_redis):
    for i in range(3):
        rc.publish_network_measurement({"package_name": f"p{i}"})

    assert len(fake_redis.data[rc.NETWORK_MEASUREMENTS_QUEUE]) == 3


def test_check_redis_connection_true(fake_redis):
    assert rc.check_redis_connection() is True


def test_check_redis_connection_false(monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise redis.RedisError("down")

    monkeypatch.setattr(rc, "redis_client", BrokenRedis())
    assert rc.check_redis_connection() is False