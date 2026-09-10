
from unittest.mock import Mock, patch

from apscheduler.schedulers.background import BackgroundScheduler

from app.api_client import ApplicationSummary
from app.crawler import runner
from app.crawler.runner import (
    CRAWL_JOB_PREFIX,
    SYNC_JOB_ID,
    CrawlSummary,
    _crawl_job_id,
    _remove_stale_jobs,
    crawl_application,
    sync_applications,
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


def test_crawl_job_id_format():
    assert _crawl_job_id("org.telegram.messenger") == (
        "crawl_app:org.telegram.messenger"
    )


@patch("app.crawler.runner.time.sleep")
@patch("app.crawler.runner.publish_reviews")
@patch("app.crawler.runner.publish_stats")
@patch("app.crawler.runner.PlayStoreCrawler")
def test_crawl_application_publishes(
    crawler_class_mock,
    publish_stats_mock,
    publish_reviews_mock,
    sleep_mock,
):
    crawler_class_mock.return_value.crawl_application.return_value = (
        {"application_id": 1},
        [{"application_id": 1}, {"application_id": 1}],
    )

    summary = crawl_application(_make_application())

    assert isinstance(summary, CrawlSummary)
    assert summary.success is True
    assert summary.stats_published == 1
    assert summary.reviews_published == 2

    publish_stats_mock.assert_called_once()
    assert publish_reviews_mock.call_count == 2
    sleep_mock.assert_called_once()


@patch("app.crawler.runner.time.sleep")
@patch("app.crawler.runner.publish_reviews")
@patch("app.crawler.runner.publish_stats")
@patch("app.crawler.runner.PlayStoreCrawler")
def test_crawl_application_skips_publish_on_failure(
    crawler_class_mock,
    publish_stats_mock,
    publish_reviews_mock,
    sleep_mock,
):
    crawler_class_mock.return_value.crawl_application.side_effect = (
        RuntimeError("boom")
    )

    summary = crawl_application(_make_application())

    assert summary.success is False
    assert summary.stats_published == 0
    assert summary.reviews_published == 0

    publish_stats_mock.assert_not_called()
    publish_reviews_mock.assert_not_called()
    sleep_mock.assert_called_once()


@patch("app.crawler.runner.publish_reviews")
@patch("app.crawler.runner.publish_stats")
@patch("app.crawler.runner.time.sleep")
def test_crawl_application_applies_random_delay(
    sleep_mock,
    publish_stats_mock,
    publish_reviews_mock,
):
    with patch(
        "app.crawler.runner.random.uniform",
        return_value=3.5,
    ) as uniform_mock:
        with patch(
            "app.crawler.runner.PlayStoreCrawler"
        ) as crawler_class_mock:
            crawler_class_mock.return_value.crawl_application.return_value = (
                {},
                [],
            )
            crawl_application(_make_application())

    uniform_mock.assert_called_once_with(
        runner.REQUEST_DELAY_MIN_SECONDS,
        runner.REQUEST_DELAY_MAX_SECONDS,
    )
    sleep_mock.assert_called_once_with(3.5)


@patch("app.crawler.runner._register_application")
@patch("app.crawler.runner.fetch_active_applications")
def test_sync_applications_registers_and_removes(
    fetch_apps_mock,
    register_mock,
):
    scheduler = BackgroundScheduler()
    scheduler.start()

    stale_job = scheduler.add_job(
        lambda: None,
        "interval",
        seconds=3600,
        id=f"{CRAWL_JOB_PREFIX}:com.old.app",
    )
    assert stale_job is not None

    fetch_apps_mock.return_value = [
        _make_application(1, "org.telegram.messenger"),
        _make_application(2, "com.whatsapp"),
    ]

    try:
        sync_applications(scheduler)
        assert register_mock.call_count == 2
        assert (
            scheduler.get_job(f"{CRAWL_JOB_PREFIX}:com.old.app") is None
        )
    finally:
        scheduler.shutdown(wait=False)


@patch("app.crawler.runner.fetch_active_applications")
def test_sync_applications_handles_api_failure(fetch_apps_mock):
    fetch_apps_mock.side_effect = RuntimeError("API is down")

    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        sync_applications(scheduler)
    finally:
        scheduler.shutdown(wait=False)


def test_remove_stale_jobs_removes_only_crawl_jobs():
    scheduler = BackgroundScheduler()
    scheduler.start()

    try:
        scheduler.add_job(
            lambda: None,
            "interval",
            seconds=3600,
            id=SYNC_JOB_ID,
        )
        scheduler.add_job(
            lambda: None,
            "interval",
            seconds=3600,
            id=f"{CRAWL_JOB_PREFIX}:com.stale.app",
        )
        scheduler.add_job(
            lambda: None,
            "interval",
            seconds=3600,
            id=f"{CRAWL_JOB_PREFIX}:com.keep.app",
        )

        _remove_stale_jobs(
            scheduler,
            active_package_names={"com.keep.app"},
        )

        assert scheduler.get_job(SYNC_JOB_ID) is not None
        assert (
            scheduler.get_job(f"{CRAWL_JOB_PREFIX}:com.stale.app")
            is None
        )
        assert (
            scheduler.get_job(f"{CRAWL_JOB_PREFIX}:com.keep.app")
            is not None
        )
    finally:
        scheduler.shutdown(wait=False)


def test_build_scheduler_returns_background_scheduler():
    scheduler = runner._build_scheduler()
    assert isinstance(scheduler, BackgroundScheduler)


@patch("app.crawler.runner.sync_applications")
@patch("app.crawler.runner._build_scheduler")
@patch("app.crawler.runner.threading.Event")
def test_run_crawler_starts_and_stops(
    event_class_mock,
    build_scheduler_mock,
    sync_applications_mock,
):
    stop_event = Mock()

    state = {"waited": False}

    def is_set_side_effect():
        return state["waited"]

    def wait_side_effect(timeout=None):
        if state["waited"]:
            return True
        state["waited"] = True
        return False

    stop_event.is_set.side_effect = is_set_side_effect
    stop_event.wait.side_effect = wait_side_effect

    event_class_mock.return_value = stop_event

    scheduler = Mock(spec=BackgroundScheduler)
    scheduler.get_jobs.return_value = []
    build_scheduler_mock.return_value = scheduler

    runner.run_crawler()

    scheduler.start.assert_called_once()
    scheduler.shutdown.assert_called_once_with(wait=True)
    sync_applications_mock.assert_called()