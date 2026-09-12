from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppReview, AppStats


def _parse_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def save_app_stats(db: Session, payload: dict) -> AppStats:
    data = payload.get("data", {})

    stats = AppStats(
        application_id=payload["application_id"],
        package_name=payload["package_name"],
        crawl_timestamp=_parse_datetime(payload.get("crawl_timestamp")),
        min_installs=data.get("minInstalls"),
        score=data.get("score"),
        ratings=data.get("ratings"),
        reviews=data.get("reviews"),
        updated=data.get("updated"),
        version=data.get("version"),
        ad_supported=data.get("adSupported"),
    )

    db.add(stats)
    db.commit()
    db.refresh(stats)

    return stats


def upsert_app_review(db: Session, payload: dict) -> AppReview:
    data = payload.get("data", {})
    package_name = payload["package_name"]
    review_id = data.get("reviewId")

    if review_id is None:
        raise ValueError("Review payload is missing reviewId")

    existing = db.scalar(
        select(AppReview).where(
            AppReview.package_name == package_name,
            AppReview.review_id == review_id,
        )
    )

    crawl_timestamp = _parse_datetime(payload.get("crawl_timestamp"))
    review_at = _parse_datetime(data.get("at"))

    if existing is not None:
        existing.user_name = data.get("userName")
        existing.thumbs_up_count = data.get("thumbsUpCount")
        existing.score = data.get("score")
        existing.content = data.get("content")
        existing.review_at = review_at
        existing.crawl_timestamp = crawl_timestamp

        db.commit()
        db.refresh(existing)

        return existing

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
    db.commit()
    db.refresh(review)

    return review