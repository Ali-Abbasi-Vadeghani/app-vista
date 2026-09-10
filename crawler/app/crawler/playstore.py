
import logging
import os
import random
from datetime import datetime, timezone
from itertools import cycle
from typing import Any, Callable

import httpx
import requests
from google_play_scraper import Sort
from google_play_scraper import app as playstore_app
from google_play_scraper import reviews as playstore_reviews
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


MAX_REVIEWS = 1000
PLAYSTORE_LANGUAGE = "en"
PLAYSTORE_COUNTRY = "us"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


PROXY_LIST_STR = os.getenv("PROXY_LIST", "")
PROXY_LIST = [p.strip() for p in PROXY_LIST_STR.split(",") if p.strip()]

proxy_pool = cycle(PROXY_LIST) if PROXY_LIST else None


class PlayStoreCrawler:


    def __init__(
        self,
        stats_fetcher: Callable[..., dict[str, Any]] = playstore_app,
        reviews_fetcher: Callable[..., Any] = playstore_reviews,
    ):
        self.stats_fetcher = stats_fetcher
        self.reviews_fetcher = reviews_fetcher

    def _get_request_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {}

        options["headers"] = {"User-Agent": random.choice(USER_AGENTS)}

        if proxy_pool:
            proxy = next(proxy_pool)
            options["proxy"] = proxy
            logger.debug("Using proxy: %s", proxy)

        return options

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def fetch_stats(self, package_name: str) -> dict[str, Any]:
        request_options = self._get_request_options()
        return self.stats_fetcher(
            package_name,
            lang=PLAYSTORE_LANGUAGE,
            country=PLAYSTORE_COUNTRY,
            **request_options,
        )

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def fetch_reviews(self, package_name: str) -> list[dict[str, Any]]:
        request_options = self._get_request_options()
        result = self.reviews_fetcher(
            package_name,
            lang=PLAYSTORE_LANGUAGE,
            country=PLAYSTORE_COUNTRY,
            sort=Sort.NEWEST,
            count=MAX_REVIEWS,
            **request_options,
        )
        reviews, _ = result
        return reviews[:MAX_REVIEWS]

    def crawl_application(
        self,
        application_id: int,
        package_name: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        crawl_timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("Starting crawl application_id=%s package=%s", application_id, package_name)

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
        logger.info("Reviews fetched package=%s count=%s", package_name, len(review_messages))

        return stats_message, review_messages