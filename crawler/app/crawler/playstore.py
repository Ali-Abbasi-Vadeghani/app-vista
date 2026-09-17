
import http.client
import logging
import os
import random
from datetime import datetime, timezone
from typing import Any, Callable

from google_play_scraper import Sort
from google_play_scraper import app as playstore_app
from google_play_scraper import reviews as playstore_reviews
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.proxy_manager import get_healthy_proxies


logger = logging.getLogger(__name__)


MAX_REVIEWS = 1000
PLAYSTORE_LANGUAGE = "en"
PLAYSTORE_COUNTRY = "us"

_crawler_instance: "PlayStoreCrawler | None" = None


class EmptyReviewsError(RuntimeError):
    pass


def get_crawler() -> "PlayStoreCrawler":
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = PlayStoreCrawler()
    return _crawler_instance


class PlayStoreCrawler:
    def __init__(
        self,
        stats_fetcher: Callable[..., dict[str, Any]] = playstore_app,
        reviews_fetcher: Callable[..., Any] = playstore_reviews,
    ):
        self.stats_fetcher = stats_fetcher
        self.reviews_fetcher = reviews_fetcher
        self.healthy_proxies: list[str] = []

        self._load_healthy_proxies()

    def _load_healthy_proxies(self) -> None:
        proxy_file = os.getenv("PROXY_FILE", "http.txt")

        if not os.path.exists(proxy_file):
            logger.info("No proxy file found at %s; running without proxies", proxy_file)
            self.healthy_proxies = []
            return

        self.healthy_proxies = get_healthy_proxies(proxy_file)

        if not self.healthy_proxies:
            logger.warning("No healthy proxies found; running without proxies")

    def _get_random_proxy(self) -> str | None:
        if not self.healthy_proxies:
            return None
        return random.choice(self.healthy_proxies)

    def _install_proxy(self, proxy: str) -> None:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy

    @retry(
        retry=retry_if_exception_type(
            (
                http.client.IncompleteRead,
                http.client.RemoteDisconnected,
                ConnectionError,
                TimeoutError,
                OSError,
            )
        ),
        wait=wait_exponential(multiplier=2, min=3, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_stats(self, package_name: str) -> dict[str, Any]:
        proxy = self._get_random_proxy()

        if proxy:
            logger.info(
                "Using proxy for stats package=%s proxy=%s",
                package_name,
                proxy,
            )
            self._install_proxy(proxy)

        return self.stats_fetcher(
            package_name,
            lang=PLAYSTORE_LANGUAGE,
            country=PLAYSTORE_COUNTRY,
        )

    @retry(
        retry=retry_if_exception_type(
            (
                EmptyReviewsError,
                http.client.IncompleteRead,
                http.client.RemoteDisconnected,
                ConnectionError,
                TimeoutError,
                OSError,
            )
        ),
        wait=wait_exponential(multiplier=2, min=3, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def fetch_reviews(self, package_name: str) -> list[dict[str, Any]]:
        proxy = self._get_random_proxy()

        if proxy:
            logger.info(
                "Using proxy for reviews package=%s proxy=%s",
                package_name,
                proxy,
            )
            self._install_proxy(proxy)

        result = self.reviews_fetcher(
            package_name,
            lang=PLAYSTORE_LANGUAGE,
            country=PLAYSTORE_COUNTRY,
            sort=Sort.NEWEST,
            count=MAX_REVIEWS,
        )

        reviews, continuation_token = result

        if not reviews:
            raise EmptyReviewsError(
                f"No reviews returned for package={package_name}"
            )

        reviews = reviews[:MAX_REVIEWS]

        logger.info(
            "Reviews fetched package=%s count=%s",
            package_name,
            len(reviews),
        )

        return reviews

    def crawl_application(
        self,
        application_id: int,
        package_name: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        crawl_timestamp = datetime.now(timezone.utc).isoformat()

        logger.info(
            "Starting crawl application_id=%s package=%s",
            application_id,
            package_name,
        )

        stats = self.fetch_stats(package_name)

        stats_message = {
            "application_id": application_id,
            "package_name": package_name,
            "crawl_timestamp": crawl_timestamp,
            "data": {
                "minInstalls": stats.get("minInstalls"),
                "score": stats.get("score"),
                "ratings": stats.get("ratings"),
                "reviews": stats.get("reviews"),
                "updated": stats.get("updated"),
                "version": stats.get("version"),
                "adSupported": stats.get("adSupported"),
            },
        }

        logger.info("Stats fetched package=%s", package_name)

        reviews = self.fetch_reviews(package_name)

        review_messages = [
            {
                "application_id": application_id,
                "package_name": package_name,
                "crawl_timestamp": crawl_timestamp,
                "data": {
                    "reviewId": review.get("reviewId"),
                    "at": review.get("at"),
                    "userName": review.get("userName"),
                    "thumbsUpCount": review.get("thumbsUpCount"),
                    "score": review.get("score"),
                    "content": review.get("content"),
                },
            }
            for review in reviews
        ]

        logger.info(
            "Reviews fetched package=%s count=%s",
            package_name,
            len(review_messages),
        )

        return stats_message, review_messages