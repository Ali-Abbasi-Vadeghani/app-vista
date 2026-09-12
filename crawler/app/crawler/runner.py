import logging
import os
import random
import signal
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api_client import ApplicationSummary, fetch_active_applications
from app.crawler.playstore import PlayStoreCrawler
from app.redis_client import publish_reviews_batch, publish_stats


logger = logging.getLogger(__name__)


CRAWL_INTERVAL_SECONDS = int(os.getenv("CRAWL_INTERVAL_SECONDS", "3600"))
JITTER_MAX_SECONDS = int(os.getenv("JITTER_MAX_SECONDS", "15"))
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "200"))
SHUTDOWN_GRACE_SECONDS = int(os.getenv("SHUTDOWN_GRACE_SECONDS", "30"))

SYNC_JOB_ID = "sync_applications"
CRAWL_JOB_PREFIX = "crawl_app"

_jobs_registered: set[str] = set()


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
    summary = CrawlSummary(
        application_id=application.id,
        package_name=application.package_name,
    )

    from app.crawler.playstore import get_crawler
    crawler = get_crawler()  

    try:
        stats_message, review_messages = crawler.crawl_application(
            application_id=application.id,
            package_name=application.package_name,
        )

        logger.info(
            "Publishing stats for %s",
            application.package_name,
        )
        publish_stats(stats_message)
        logger.info(
            "Stats published for %s",
            application.package_name,
        )

        publish_reviews_batch(review_messages)

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

    return summary


def _crawl_job(application: ApplicationSummary) -> None:

    jitter = random.uniform(0, JITTER_MAX_SECONDS)
    logger.info(
        "Crawl job starting for %s after %.1fs jitter",
        application.package_name,
        jitter,
    )
    time.sleep(jitter)

    try:
        crawl_application(application)
    except Exception:
        logger.exception(
            "Unhandled error in crawl job for package=%s",
            application.package_name,
        )


def _schedule_application(
    scheduler: BackgroundScheduler,
    application: ApplicationSummary,
) -> None:
    job_id = f"{CRAWL_JOB_PREFIX}:{application.package_name}"

    if job_id in _jobs_registered:
        logger.debug("Job already registered: %s", job_id)
        return

    scheduler.add_job(
        _crawl_job,
        trigger=IntervalTrigger(seconds=CRAWL_INTERVAL_SECONDS),
        args=[application],
        id=job_id,
        name=f"Crawl {application.package_name}",
        replace_existing=False,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
        next_run_time=datetime.now(timezone.utc),
    )

    _jobs_registered.add(job_id)
    logger.info("Scheduled crawl job for %s", application.package_name)


def _remove_job(scheduler: BackgroundScheduler, job_id: str) -> None:
    try:
        scheduler.remove_job(job_id)
        _jobs_registered.discard(job_id)
        logger.info("Removed job %s", job_id)
    except Exception:
        logger.exception("Failed to remove job %s", job_id)


def _sync_applications(scheduler: BackgroundScheduler) -> None:
    try:
        applications = fetch_active_applications()
    except Exception:
        logger.exception("Failed to fetch active applications from the API")
        return

    active_package_names = {app.package_name for app in applications}
    scheduled_package_names = {
        job_id.split(":", 1)[1] for job_id in _jobs_registered
    }

    added = 0
    for application in applications:
        if application.package_name in scheduled_package_names:
            continue
        logger.info("Scheduling new crawl job for %s", application.package_name)
        _schedule_application(scheduler, application)
        added += 1

    removed = 0
    for package_name in scheduled_package_names - active_package_names:
        _remove_job(scheduler, f"{CRAWL_JOB_PREFIX}:{package_name}")
        removed += 1

    logger.info(
        "Sync complete: %s active, %s added, %s removed",
        len(applications),
        added,
        removed,
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
        "Crawler starting: interval=%ss, jitter_max=%ss, sync=%ss",
        CRAWL_INTERVAL_SECONDS,
        JITTER_MAX_SECONDS,
        SYNC_INTERVAL_SECONDS,
    )


    from app.crawler.playstore import get_crawler
    get_crawler() 

    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 60,
        },
    )

    _sync_applications(scheduler)

    scheduler.add_job(
        _sync_applications,
        trigger=IntervalTrigger(seconds=SYNC_INTERVAL_SECONDS),
        args=[scheduler],
        id=SYNC_JOB_ID,
        name="Sync active applications",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(timezone.utc),
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