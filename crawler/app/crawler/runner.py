

import logging
import os
import random
import signal
import threading
import time
from dataclasses import asdict, dataclass

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api_client import ApplicationSummary, fetch_active_applications
from app.crawler.playstore import PlayStoreCrawler
from app.redis_client import publish_reviews, publish_stats

logger = logging.getLogger(__name__)

CRAWL_INTERVAL_SECONDS = int(os.getenv("CRAWL_INTERVAL_SECONDS", "3600"))
REQUEST_DELAY_MIN_SECONDS = float(os.getenv("REQUEST_DELAY_MIN_SECONDS", "2"))
REQUEST_DELAY_MAX_SECONDS = float(os.getenv("REQUEST_DELAY_MAX_SECONDS", "5"))
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
SHUTDOWN_GRACE_SECONDS = int(os.getenv("SHUTDOWN_GRACE_SECONDS", "30"))
SYNC_JOB_ID = "sync_applications"
CRAWL_JOB_PREFIX = "crawl_app"


@dataclass
class CrawlSummary:
    application_id: int
    package_name: str
    stats_published: int = 0
    reviews_published: int = 0
    success: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def crawl_application(application: ApplicationSummary) -> CrawlSummary:
    summary = CrawlSummary(application_id=application.id, package_name=application.package_name)
    crawler = PlayStoreCrawler()

    try:
        stats_message, review_messages = crawler.crawl_application(
            application_id=application.id,
            package_name=application.package_name,
        )

        publish_stats(stats_message)
        for review_message in review_messages:
            publish_reviews(review_message)

        summary.stats_published = 1
        summary.reviews_published = len(review_messages)
        summary.success = True
        logger.info(
            "Crawl completed id=%s package=%s reviews=%s",
            application.id,
            application.package_name,
            len(review_messages),
        )
    except Exception:
        logger.exception(
            "Crawl failed id=%s package=%s",
            application.id,
            application.package_name,
        )

    delay = random.uniform(REQUEST_DELAY_MIN_SECONDS, REQUEST_DELAY_MAX_SECONDS)
    logger.info("Waiting for %.2f seconds before next application...", delay)
    time.sleep(delay)

    return summary


def _crawl_job(application: ApplicationSummary) -> None:
    try:
        crawl_application(application)
    except Exception:
        logger.exception("Unhandled error in crawl job for package=%s", application.package_name)


def _crawl_job_id(package_name: str) -> str:
    return f"{CRAWL_JOB_PREFIX}:{package_name}"


def _register_application(scheduler: BackgroundScheduler, application: ApplicationSummary) -> None:
    scheduler.add_job(
        _crawl_job,
        trigger=IntervalTrigger(seconds=CRAWL_INTERVAL_SECONDS),
        args=[application],
        id=_crawl_job_id(application.package_name),
        name=f"Crawl {application.package_name}",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60,
    )


def _remove_stale_jobs(scheduler: BackgroundScheduler, active_package_names: set[str]) -> None:
    for job in scheduler.get_jobs():
        if not job.id.startswith(CRAWL_JOB_PREFIX + ":"):
            continue
        package_name = job.id.split(":", 1)[1]
        if package_name not in active_package_names:
            logger.info("Removing stale crawl job for %s", package_name)
            scheduler.remove_job(job.id)


def sync_applications(scheduler: BackgroundScheduler) -> None:
    try:
        applications = fetch_active_applications()
    except Exception:
        logger.exception("Failed to fetch active applications from the API")
        return

    active_package_names = {app.package_name for app in applications}
    for application in applications:
        _register_application(scheduler, application)
    _remove_stale_jobs(scheduler, active_package_names)

    logger.info("Scheduler synced: %s active applications", len(applications))


def _build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 60},
    )


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def _handle_signal(signum, _frame):
        logger.info("Received signal %s; requesting shutdown...", signum)
        stop_event.set()
    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        try:
            signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, OSError):
            logger.debug("SIGTERM not installable on this platform")


def run_crawler() -> None:
    logger.info(
        "Crawler starting: per-app interval=%ss, sync interval=%ss",
        CRAWL_INTERVAL_SECONDS,
        SYNC_INTERVAL_SECONDS,
    )

    scheduler = _build_scheduler()
    sync_applications(scheduler)

    scheduler.add_job(
        sync_applications,
        trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
        args=[scheduler],
        id=SYNC_JOB_ID,
        name="Sync active applications",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    scheduler.start()
    logger.info("Scheduler started with %s jobs", len(scheduler.get_jobs()))

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1)
    finally:
        logger.info("Shutting down scheduler (grace=%ss)...", SHUTDOWN_GRACE_SECONDS)
        scheduler.shutdown(wait=True)
        logger.info("Crawler stopped.")