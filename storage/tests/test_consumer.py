from unittest.mock import patch

from app import consumer
from app.consumer import process_message
from app.redis_client import REVIEWS_QUEUE, STATS_QUEUE


@patch("app.consumer.save_app_stats")
def test_process_stats_message(save_stats_mock):
    payload = {
        "application_id": 1,
        "package_name": "org.telegram.messenger",
        "data": {"score": 4.5},
    }

    result = process_message(STATS_QUEUE, payload, db=None)

    assert result is True
    save_stats_mock.assert_called_once()


@patch("app.consumer.upsert_app_review")
def test_process_reviews_message(upsert_review_mock):
    payload = {
        "application_id": 1,
        "package_name": "org.telegram.messenger",
        "data": {"reviewId": "review-1"},
    }

    result = process_message(REVIEWS_QUEUE, payload, db=None)

    assert result is True
    upsert_review_mock.assert_called_once()


@patch("app.consumer.save_app_stats")
def test_process_unknown_queue(save_stats_mock):
    result = process_message("unknown:queue", {}, db=None)

    assert result is False
    save_stats_mock.assert_not_called()


@patch("app.consumer.upsert_app_review")
def test_process_message_rolls_back_on_error(upsert_review_mock):
    class FakeDB:
        def __init__(self):
            self.rolled_back = False

        def rollback(self):
            self.rolled_back = True

    fake_db = FakeDB()
    upsert_review_mock.side_effect = RuntimeError("boom")

    result = process_message(REVIEWS_QUEUE, {"data": {}}, db=fake_db)

    assert result is False
    assert fake_db.rolled_back is True


@patch("app.consumer.dequeue_message", return_value=None)
def test_consume_once_returns_false_on_timeout(dequeue_mock):
    result = consumer.consume_once()

    assert result is False


@patch("app.consumer.SessionLocal")
@patch("app.consumer.process_message")
@patch("app.consumer.dequeue_message")
def test_consume_once_returns_true_when_message_processed(
    dequeue_mock,
    process_mock,
    session_local_mock,
):
    dequeue_mock.return_value = (STATS_QUEUE, {"application_id": 1})

    db_instance = session_local_mock.return_value

    result = consumer.consume_once()

    assert result is True
    process_mock.assert_called_once()
    db_instance.close.assert_called_once()