
import logging
import time

from sqlalchemy import select

from app.database import SessionLocal
from app.models import AppReview, AppStats
from app.redis_client import (
    dequeue_network_measurement,
    dequeue_reviews,
    dequeue_stats,
    get_queue_lengths,
)
from app.repository import (
    _parse_datetime,
    save_network_measurement_no_commit,
)


logger = logging.getLogger(__name__)


BATCH_SIZE = 200
PER_QUEUE_LIMIT = BATCH_SIZE

IDLE_LOG_EVERY_SECONDS = 60


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


def _bulk_upsert_reviews(db, payloads: list[dict]) -> tuple[int, int]:
    grouped: dict[str, list[dict]] = {}
    for payload in payloads:
        review_id = payload.get("data", {}).get("reviewId")
        if review_id is None:
            logger.warning(
                "Skipping review without reviewId package=%s",
                payload.get("package_name"),
            )
            continue
        grouped.setdefault(payload["package_name"], []).append(payload)

    if not grouped:
        return 0, 0

    existing_reviews: dict[tuple[str, str], AppReview] = {}
    for package_name, items in grouped.items():
        review_ids = [item["data"]["reviewId"] for item in items]

        rows = db.scalars(
            select(AppReview).where(
                AppReview.package_name == package_name,
                AppReview.review_id.in_(review_ids),
            )
        ).all()

        for row in rows:
            existing_reviews[(row.package_name, row.review_id)] = row

    inserted = 0
    updated = 0

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
            updated += 1
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
        inserted += 1

    return inserted, updated


def _drain_queue(dequeue_fn, limit: int) -> list[dict]:
    items: list[dict] = []
    for _ in range(limit):
        payload = dequeue_fn()
        if payload is None:
            break
        items.append(payload)
    return items


def consume_once() -> int:
    db = SessionLocal()
    processed = 0

    try:
        stats_payloads = _drain_queue(dequeue_stats, PER_QUEUE_LIMIT)
        if stats_payloads:
            stats_to_insert = [_build_stats_dict(p) for p in stats_payloads]
            db.bulk_insert_mappings(AppStats, stats_to_insert)
            processed += len(stats_to_insert)
            logger.info("Staged %s app_stats rows", len(stats_to_insert))

        review_payloads = _drain_queue(dequeue_reviews, PER_QUEUE_LIMIT)
        if review_payloads:
            inserted, updated = _bulk_upsert_reviews(db, review_payloads)
            processed += len(review_payloads)
            logger.info(
                "Staged reviews: inserted=%s updated=%s",
                inserted,
                updated,
            )

        network_payloads = _drain_queue(
            dequeue_network_measurement, PER_QUEUE_LIMIT
        )
        staged_network = 0
        failed_network = 0

        for payload in network_payloads:
            savepoint = db.begin_nested()
            try:
                save_network_measurement_no_commit(db, payload)
                savepoint.commit()
                staged_network += 1
                processed += 1
            except Exception:
                savepoint.rollback()
                failed_network += 1
                logger.exception(
                    "Failed to stage network measurement package=%s scenario=%s",
                    payload.get("package_name"),
                    payload.get("scenario"),
                )

        if network_payloads:
            logger.info(
                "Staged network measurements: ok=%s failed=%s",
                staged_network,
                failed_network,
            )

        if processed > 0:
            db.commit()
            logger.info("Committed %s messages", processed)

    except Exception:
        db.rollback()
        logger.exception("Failed to commit batch; rolled back")
        processed = 0
    finally:
        db.close()

    return processed


def _log_idle_queue_lengths() -> None:
    lengths = get_queue_lengths()
    if lengths:
        logger.info(
            "Idle — queue lengths: stats=%s reviews=%s network=%s",
            lengths.get("stats"),
            lengths.get("reviews"),
            lengths.get("network"),
        )


def run_consumer() -> None:
    logger.info(
        "Storage consumer started: batch_size=%s per_queue_limit=%s",
        BATCH_SIZE,
        PER_QUEUE_LIMIT,
    )

    last_idle_log = time.monotonic()

    while True:
        try:
            processed = consume_once()

            if processed == 0:
                now = time.monotonic()
                if now - last_idle_log >= IDLE_LOG_EVERY_SECONDS:
                    _log_idle_queue_lengths()
                    last_idle_log = now
                time.sleep(1)
            else:
                last_idle_log = time.monotonic()

        except Exception:
            logger.exception("Unexpected consumer error")
            time.sleep(1)