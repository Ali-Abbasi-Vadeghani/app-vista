import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AppReview, AppStats
from app.repository import save_app_stats, upsert_app_review


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _stats_payload():
    return {
        "application_id": 1,
        "package_name": "org.telegram.messenger",
        "crawl_timestamp": "2026-09-10T10:00:00+00:00",
        "data": {
            "minInstalls": 1000000,
            "score": 4.5,
            "ratings": 50000,
            "reviews": 10000,
            "updated": "2026-09-01",
            "version": "1.0.0",
            "adSupported": True,
        },
    }


def _review_payload(review_id="review-1", content="Great app"):
    return {
        "application_id": 1,
        "package_name": "org.telegram.messenger",
        "crawl_timestamp": "2026-09-10T10:00:00+00:00",
        "data": {
            "reviewId": review_id,
            "at": "2026-09-09T12:00:00",
            "userName": "Test User",
            "thumbsUpCount": 5,
            "score": 5,
            "content": content,
        },
    }


def test_save_app_stats(db):
    stats = save_app_stats(db, _stats_payload())

    assert stats.id is not None
    assert stats.package_name == "org.telegram.messenger"
    assert stats.min_installs == 1000000
    assert stats.score == 4.5
    assert stats.ad_supported is True


def test_save_app_stats_multiple_rows(db):
    save_app_stats(db, _stats_payload())
    save_app_stats(db, _stats_payload())

    rows = db.query(AppStats).all()

    assert len(rows) == 2


def test_upsert_app_review_inserts_new(db):
    review = upsert_app_review(db, _review_payload())

    assert review.id is not None
    assert review.review_id == "review-1"
    assert review.thumbs_up_count == 5
    assert review.content == "Great app"


def test_upsert_app_review_updates_existing(db):
    upsert_app_review(db, _review_payload(content="First version"))
    updated = upsert_app_review(db, _review_payload(content="Updated version"))

    rows = db.query(AppReview).all()

    assert len(rows) == 1
    assert updated.content == "Updated version"


def test_upsert_app_review_without_review_id(db):
    payload = _review_payload()
    payload["data"]["reviewId"] = None

    with pytest.raises(ValueError):
        upsert_app_review(db, payload)