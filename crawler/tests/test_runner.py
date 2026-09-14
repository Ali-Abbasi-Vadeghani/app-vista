
from unittest.mock import Mock, patch

from apscheduler.schedulers.background import BackgroundScheduler

from app.api_client import ApplicationSummary
from app.crawler import runner
from app.crawler.runner import (
    CRAWL_JOB_PREFIX,
    SYNC_JOB_ID,
    CrawlSummary,
    _crawl_job,
    _remove_job,
    _schedule_application,
    _sync_applications,
    crawl_application,
)


def _make_application(
    app_id: int = 1,
    package_name: str = "org.telegram.messenger",
) -> ApplicationSummary:
    return ApplicationSummary(
        id=app_id,
        name="Test",
        package_name=package_name,
        category="Social",
        is_active=True,
    )


@patch("app.crawler.runner.publish_reviews_batch")
@patch("app.crawler.runner.publish_stats")
@patch("app.crawler.playstore.get_crawler")
def test_crawl_application_publishes(
    get_crawler_mock,
    publish_stats_mock,
    publish_reviews_batch_mock,
):
    crawler_instance = Mock()
    crawler_instance.crawl_application.return_value = (
        {"application_id": 1, "package_name": "org.telegram.messenger"},
        [
            {"application_id": 1, "package_name": "org.telegram.messenger"},
            {"application_id": 1, "package_name": "org.telegram.messenger"},
        ],
    )
    get_crawler_mock.return_value = crawler_instance

    summary = crawl_application(_make_application())

    assert isinstance(summary, CrawlSummary)
    assert summary.success is True
    assert summary.stats_published == 1
    assert summary.reviews_published == 2

    publish_stats_mock.assert_called_once()
    publish_reviews_batch_mock.assert_called_once()
    batch_arg = publish_reviews_batch_mock.call_args[0][0]
    assert len(batch_arg) == 2


@patch("app.crawler.runner.publish_reviews_batch")
@patch("app.crawler.runner.publish_stats")
@patch("app.crawler.playstore.get_crawler")
def test_crawl_application_skips_publish_on_failure(
    get_crawler_mock,
    publish_stats_mock,
    publish_reviews_batch_mock,
):
    crawler_instance = Mock()
    crawler_instance.crawl_application.side_effect = RuntimeError("boom")
    get_crawler_mock.return_value = crawler_instance

    summary = crawl_application(_make_application())

    assert summary.success is False
    assert summary.stats_published == 0
    assert summary.reviews_published == 0

    publish_stats_mock.assert_not_called()
    publish_reviews_batch_mock.assert_not_called()


@patch("app.crawler.runner.time.sleep")
@patch("app.crawler.runner.crawl_application")
@patch("app.crawler.runner.random.uniform", return_value=42.5)
def test_crawl_job_applies_jitter(
    uniform_mock,
    crawl_mock,
    sleep_mock,
):
    _crawl_job(_make_application())

    uniform_mock.assert_called_once_with(0, runner.JITTER_MAX_SECONDS)
    sleep_mock.assert_called_once_with(42.5)
    crawl_mock.assert_called_once()


@patch("app.crawler.runner.time.sleep")
@patch("app.crawler.runner.crawl_application")
@patch("app.crawler.runner.random.uniform", return_value=10.0)
def test_crawl_job_handles_crawl_exception(
    uniform_mock,
    crawl_mock,
    sleep_mock,
):
    crawl_mock.side_effect = RuntimeError("boom")

    _crawl_job(_make_application())

    crawl_mock.assert_called_once()
    sleep_mock.assert_called_once_with(10.0)


def test_schedule_application_registers_job():
    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        application = _make_application()

        runner._jobs_registered.clear()
        _schedule_application(scheduler, application)

        job = scheduler.get_job(
            f"{CRAWL_JOB_PREFIX}:{application.package_name}"
        )

        assert job is not None
        assert job.id == f"{CRAWL_JOB_PREFIX}:{application.package_name}"
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


def test_schedule_application_skips_if_already_registered():
    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        application = _make_application()
        runner._jobs_registered.clear()
        runner._jobs_registered.add(
            f"{CRAWL_JOB_PREFIX}:{application.package_name}"
        )

        _schedule_application(scheduler, application)

        assert (
            scheduler.get_job(
                f"{CRAWL_JOB_PREFIX}:{application.package_name}"
            )
            is None
        )
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


def test_remove_job_removes_job():
    scheduler = BackgroundScheduler()
    scheduler.start()

    scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id="dummy",
    )

    try:
        runner._jobs_registered.add("dummy")
        _remove_job(scheduler, "dummy")
        assert scheduler.get_job("dummy") is None
        assert "dummy" not in runner._jobs_registered
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


def test_remove_job_handles_missing_job():
    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        _remove_job(scheduler, "does-not-exist")
    finally:
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner._schedule_application")
@patch("app.crawler.runner.fetch_active_applications")
def test_sync_registers_only_new_apps(
    fetch_apps_mock,
    schedule_mock,
):
    scheduler = BackgroundScheduler()
    scheduler.start()

    scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id=f"{CRAWL_JOB_PREFIX}:org.telegram.messenger",
    )
    runner._jobs_registered.clear()
    runner._jobs_registered.add(
        f"{CRAWL_JOB_PREFIX}:org.telegram.messenger"
    )

    fetch_apps_mock.return_value = [
        _make_application(1, "org.telegram.messenger"),
        _make_application(2, "com.whatsapp"),
    ]

    try:
        _sync_applications(scheduler)

        assert schedule_mock.call_count == 1
        scheduled_app = schedule_mock.call_args[0][1]
        assert scheduled_app.package_name == "com.whatsapp"
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner.fetch_active_applications")
def test_sync_removes_stale_jobs(fetch_apps_mock):
    scheduler = BackgroundScheduler()
    scheduler.start()

    scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id=f"{CRAWL_JOB_PREFIX}:com.old.app",
    )
    scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id=f"{CRAWL_JOB_PREFIX}:org.telegram.messenger",
    )

    runner._jobs_registered.clear()
    runner._jobs_registered.add(f"{CRAWL_JOB_PREFIX}:com.old.app")
    runner._jobs_registered.add(
        f"{CRAWL_JOB_PREFIX}:org.telegram.messenger"
    )

    fetch_apps_mock.return_value = [
        _make_application(1, "org.telegram.messenger"),
    ]

    try:
        _sync_applications(scheduler)

        assert (
            scheduler.get_job(f"{CRAWL_JOB_PREFIX}:com.old.app") is None
        )
        assert (
            scheduler.get_job(f"{CRAWL_JOB_PREFIX}:org.telegram.messenger")
            is not None
        )
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner.fetch_active_applications")
def test_sync_does_not_touch_existing_jobs(fetch_apps_mock):
    scheduler = BackgroundScheduler()
    scheduler.start()

    job = scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id=f"{CRAWL_JOB_PREFIX}:org.telegram.messenger",
    )
    original_next_run = job.next_run_time

    runner._jobs_registered.clear()
    runner._jobs_registered.add(
        f"{CRAWL_JOB_PREFIX}:org.telegram.messenger"
    )

    fetch_apps_mock.return_value = [
        _make_application(1, "org.telegram.messenger"),
    ]

    try:
        _sync_applications(scheduler)

        same_job = scheduler.get_job(
            f"{CRAWL_JOB_PREFIX}:org.telegram.messenger"
        )
        assert same_job.next_run_time == original_next_run
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner.fetch_active_applications")
def test_sync_handles_api_failure(fetch_apps_mock):
    fetch_apps_mock.side_effect = RuntimeError("API is down")

    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        _sync_applications(scheduler)
    finally:
        runner._jobs_registered.clear()
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner._sync_applications")
@patch("app.crawler.runner.threading.Event")
@patch("app.crawler.runner.BackgroundScheduler")
def test_run_crawler_starts_and_stops(
    scheduler_class_mock,
    event_class_mock,
    sync_mock,
):
    scheduler = Mock()
    scheduler.get_jobs.return_value = []
    scheduler_class_mock.return_value = scheduler

    stop_event = Mock()
    stop_event.is_set.return_value = True
    event_class_mock.return_value = stop_event

    runner.run_crawler()

    scheduler.start.assert_called_once()
    scheduler.shutdown.assert_called_once_with(wait=True)
    sync_mock.assert_called()