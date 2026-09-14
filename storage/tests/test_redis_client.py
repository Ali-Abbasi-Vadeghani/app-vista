
import json

import pytest

from app import redis_client as rc


class FakeRedis:
    def __init__(self):
        self.data: dict[str, list[str]] = {}

    def lpop(self, queue):
        items = self.data.get(queue, [])
        if not items:
            return None
        return items.pop(0)

    def rpush(self, queue, payload):
        self.data.setdefault(queue, []).append(payload)

    def ping(self):
        return True


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(rc, "redis_client", fake)
    return fake


def test_dequeue_stats_returns_payload(fake_redis):
    payload = {"package_name": "x", "data": {"score": 4}}
    fake_redis.rpush(rc.STATS_QUEUE, json.dumps(payload))

    assert rc.dequeue_stats() == payload


def test_dequeue_reviews_returns_payload(fake_redis):
    payload = {"package_name": "x", "data": {"reviewId": "r1"}}
    fake_redis.rpush(rc.REVIEWS_QUEUE, json.dumps(payload))

    assert rc.dequeue_reviews() == payload


def test_dequeue_network_measurement_returns_payload(fake_redis):
    payload = {"package_name": "x", "scenario": "upload"}
    fake_redis.rpush(rc.NETWORK_MEASUREMENTS_QUEUE, json.dumps(payload))

    assert rc.dequeue_network_measurement() == payload


def test_dequeue_fifo_order(fake_redis):
    fake_redis.rpush(rc.STATS_QUEUE, json.dumps({"n": 1}))
    fake_redis.rpush(rc.STATS_QUEUE, json.dumps({"n": 2}))

    assert rc.dequeue_stats() == {"n": 1}
    assert rc.dequeue_stats() == {"n": 2}


def test_check_redis_connection_false(monkeypatch):
    import redis

    class BrokenRedis:
        def ping(self):
            raise redis.RedisError("down")

    monkeypatch.setattr(rc, "redis_client", BrokenRedis())
    assert rc.check_redis_connection() is False