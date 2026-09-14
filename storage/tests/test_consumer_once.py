
import pytest

from app import consumer as consumer_module
from app.models import AppReview, AppStats, NetworkMeasurement


@pytest.fixture
def fake_queues(monkeypatch):
    state = {
        "stats": [],
        "reviews": [],
        "network": [],
    }

    def make_dequeue(key):
        def _dequeue():
            if not state[key]:
                return None
            return state[key].pop(0)
        return _dequeue

    monkeypatch.setattr(
        consumer_module, "dequeue_stats", make_dequeue("stats")
    )
    monkeypatch.setattr(
        consumer_module, "dequeue_reviews", make_dequeue("reviews")
    )
    monkeypatch.setattr(
        consumer_module, "dequeue_network_measurement", make_dequeue("network")
    )

    return state


@pytest.fixture
def patched_session(monkeypatch, db_session):
    monkeypatch.setattr(
        consumer_module, "SessionLocal", lambda: db_session
    )
    return db_session


def test_consume_once_empty(fake_queues, patched_session):
    processed = consumer_module.consume_once()
    assert processed == 0


def test_consume_once_all_queues(
    fake_queues,
    patched_session,
    stats_payload,
    review_payload,
    network_payload,
):
    fake_queues["stats"].append(stats_payload)
    fake_queues["reviews"].append(review_payload)
    fake_queues["network"].append(network_payload)

    processed = consumer_module.consume_once()
    assert processed == 3

    assert patched_session.query(AppStats).count() == 1
    assert patched_session.query(AppReview).count() == 1
    assert patched_session.query(NetworkMeasurement).count() == 1


def test_consume_once_round_robin_not_starving(
    fake_queues,
    patched_session,
    stats_payload,
    review_payload,
):
    fake_queues["stats"].append(stats_payload)

    second_stats = dict(stats_payload)
    second_stats["crawl_timestamp"] = "2024-06-01T13:00:00+00:00"
    fake_queues["stats"].append(second_stats)

    fake_queues["reviews"].append(review_payload)

    second_review = dict(review_payload)
    second_review["data"] = dict(review_payload["data"])
    second_review["data"]["reviewId"] = "rev-002"
    fake_queues["reviews"].append(second_review)

    processed = consumer_module.consume_once()
    assert processed == 4

    assert patched_session.query(AppStats).count() == 2
    assert patched_session.query(AppReview).count() == 2


def test_consume_once_network_failure_isolated(
    fake_queues,
    patched_session,
    stats_payload,
):
    fake_queues["stats"].append(stats_payload)
    fake_queues["network"].append({"invalid": "payload"})

    processed = consumer_module.consume_once()

    assert patched_session.query(AppStats).count() == 1
    assert patched_session.query(NetworkMeasurement).count() == 0
    assert processed >= 1