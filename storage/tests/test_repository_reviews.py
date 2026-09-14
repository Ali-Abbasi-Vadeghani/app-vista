
import pytest

from app.models import AppReview
from app.repository import upsert_app_review


def test_upsert_review_inserts_new(db_session, review_payload):
    review = upsert_app_review(db_session, review_payload)

    assert review.id is not None
    assert review.package_name == "com.test.app"
    assert review.review_id == "rev-001"
    assert review.user_name == "alice"
    assert review.thumbs_up_count == 5
    assert review.score == 5
    assert review.content == "great app"


def test_upsert_review_updates_existing(db_session, review_payload):
    upsert_app_review(db_session, review_payload)

    updated = dict(review_payload)
    updated["data"] = dict(review_payload["data"])
    updated["data"]["userName"] = "bob"
    updated["data"]["thumbsUpCount"] = 10
    updated["data"]["content"] = "updated content"

    upsert_app_review(db_session, updated)

    rows = db_session.query(AppReview).all()
    assert len(rows) == 1
    assert rows[0].user_name == "bob"
    assert rows[0].thumbs_up_count == 10
    assert rows[0].content == "updated content"


def test_upsert_review_different_review_ids(db_session, review_payload):
    upsert_app_review(db_session, review_payload)

    second = dict(review_payload)
    second["data"] = dict(review_payload["data"])
    second["data"]["reviewId"] = "rev-002"
    upsert_app_review(db_session, second)

    rows = db_session.query(AppReview).all()
    assert len(rows) == 2


def test_upsert_review_missing_review_id(db_session, review_payload):
    payload = dict(review_payload)
    payload["data"] = dict(review_payload["data"])
    payload["data"]["reviewId"] = None

    with pytest.raises(ValueError):
        upsert_app_review(db_session, payload)


def test_upsert_review_unique_constraint(db_session, review_payload):
    upsert_app_review(db_session, review_payload)
    upsert_app_review(db_session, review_payload)

    rows = db_session.query(AppReview).all()
    assert len(rows) == 1