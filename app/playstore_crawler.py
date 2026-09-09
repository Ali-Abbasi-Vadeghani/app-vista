from datetime import datetime, timezone

from google_play_scraper import app as playstore_app
from sqlalchemy.orm import Session

from app.crud import get_active_applications
from app.redis_client import push_playstore_stats


def crawl_application_stats(db: Session) -> int:
    applications = get_active_applications(db)

    processed_count = 0

    for application in applications:
        try:
            data = playstore_app(
                application.package_name,
                lang="en",
                country="us",
            )

            stats = {
                "application_id": application.id,
                "package_name": application.package_name,
                "name": application.name,
                "crawl_timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
                "minInstalls": data.get("minInstalls"),
                "score": data.get("score"),
                "ratings": data.get("ratings"),
                "reviews": data.get("reviews"),
                "updated": data.get("updated"),
                "version": data.get("version"),
                "adSupported": data.get("adSupported"),
            }

            push_playstore_stats(stats)

            processed_count += 1

        except Exception as exc:
            print(
                f"Failed to crawl "
                f"{application.package_name}: {exc}"
            )

    return processed_count