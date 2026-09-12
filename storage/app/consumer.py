import logging
import time

from sqlalchemy import or_, select

from app.database import SessionLocal
from app.models import AppReview, AppStats
from app.redis_client import dequeue_reviews, dequeue_stats
from app.repository import _parse_datetime


logger = logging.getLogger(__name__)


BATCH_SIZE = 200


def _build_stats_dict(payload: dict) -> dict:
    data = payload.get("data", {})

    return {
        "application_id": payload["application_id"],
        "package_name": payload["package_name"],
        "crawl_timestamp": _parse_datetime(payload.get("crawl_timestamp")),
        "min_installs": data.get("minInstalls"),
        "score": data.get("score"),
        "ratings": data.get("ratings"),
        "reviews": data.get("reviews"),
        "updated": data.get("updated"),
        "version": data.get("version"),
        "ad_supported": data.get("adSupported"),
    }


def _bulk_upsert_reviews(db, payloads: list[dict]) -> None:
    pairs = [
        (p["package_name"], p["data"].get("reviewId"))
        for p in payloads
        if p.get("data", {}).get("reviewId")
    ]

    if not pairs:
        return

    conditions = [
        (AppReview.package_name == pkg) & (AppReview.review_id == rid)
        for pkg, rid in pairs
    ]

    existing_reviews = {
        (r.package_name, r.review_id): r
        for r in db.scalars(
            select(AppReview).where(or_(*conditions))
        ).all()
    }

    for payload in payloads:
        data = payload.get("data", {})
        package_name = payload["package_name"]
        review_id = data.get("reviewId")

        if review_id is None:
            continue

        crawl_timestamp = _parse_datetime(payload.get("crawl_timestamp"))
        review_at = _parse_datetime(data.get("at"))
        existing = existing_reviews.get((package_name, review_id))

        if existing is not None:
            existing.user_name = data.get("userName")
            existing.thumbs_up_count = data.get("thumbsUpCount")
            existing.score = data.get("score")
            existing.content = data.get("content")
            existing.review_at = review_at
            existing.crawl_timestamp = crawl_timestamp
            continue

        review = AppReview(
            application_id=payload["application_id"],
            package_name=package_name,
            review_id=review_id,
            review_at=review_at,
            user_name=data.get("userName"),
            thumbs_up_count=data.get("thumbsUpCount"),
            score=data.get("score"),
            content=data.get("content"),
            crawl_timestamp=crawl_timestamp,
        )
        db.add(review)


def consume_once() -> int:
    db = SessionLocal()
    stats_to_insert: list[dict] = []
    reviews_to_upsert: list[dict] = []
    processed = 0

    try:
        for _ in range(BATCH_SIZE):
            stats_payload = dequeue_stats()

            if stats_payload is not None:
                stats_to_insert.append(_build_stats_dict(stats_payload))
                processed += 1
                continue

            review_payload = dequeue_reviews()

            if review_payload is not None:
                reviews_to_upsert.append(review_payload)
                processed += 1
                continue

            break

        if stats_to_insert:
            db.bulk_insert_mappings(AppStats, stats_to_insert)

        if reviews_to_upsert:
            _bulk_upsert_reviews(db, reviews_to_upsert)

        if processed > 0:
            db.commit()
            logger.info("Committed %s messages", processed)

    except Exception:
        db.rollback()
        logger.exception("Failed to commit batch")
    finally:
        db.close()

    return processed


def run_consumer() -> None:
    logger.info("Storage consumer started")

    while True:
        try:
            processed = consume_once()

            if processed == 0:
                time.sleep(1)  

        except Exception:
            logger.exception("Unexpected consumer error")
            time.sleep(1)