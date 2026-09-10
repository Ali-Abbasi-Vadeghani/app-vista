
import random
from unittest.mock import Mock, patch

import pytest

from app.crawler.playstore import (
    MAX_REVIEWS,
    PROXY_LIST,
    USER_AGENTS,
    PlayStoreCrawler,
)


def _fake_stats():
    return {
        "minInstalls": 1000000,
        "score": 4.5,
        "ratings": 50000,
        "reviews": 10000,
        "updated": 1700000000,
        "version": "1.0.0",
        "adSupported": True,
    }


def _fake_reviews(count: int = 1):
    return [
        {
            "reviewId": f"review-{i}",
            "at": "2026-01-01T10:00:00",
            "userName": "Test User",
            "thumbsUpCount": i,
            "score": 5,
            "content": "Excellent application",
        }
        for i in range(count)
    ]


def test_max_reviews_is_1000():
    assert MAX_REVIEWS == 1000


def test_user_agents_list_is_not_empty():
    assert len(USER_AGENTS) > 0
    assert all(isinstance(ua, str) for ua in USER_AGENTS)


def test_get_request_options_includes_user_agent():
    crawler = PlayStoreCrawler()

    options = crawler._get_request_options()

    assert "headers" in options
    assert "User-Agent" in options["headers"]
    assert options["headers"]["User-Agent"] in USER_AGENTS


def test_get_request_options_includes_proxy_when_available():
    crawler = PlayStoreCrawler()

    with patch(
        "app.crawler.playstore.proxy_pool",
        iter(["http://proxy1:8080", "http://proxy2:8080"]),
    ):
        options = crawler._get_request_options()

    assert "proxy" in options
    assert options["proxy"] in ["http://proxy1:8080", "http://proxy2:8080"]


def test_get_request_options_without_proxy():
    crawler = PlayStoreCrawler()

    with patch("app.crawler.playstore.proxy_pool", None):
        options = crawler._get_request_options()

    assert "proxy" not in options


def test_fetch_stats_passes_anti_blocking_options():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)

    with patch(
        "app.crawler.playstore.proxy_pool",
        iter(["http://proxy:8080"]),
    ):
        with patch.object(
            random,
            "choice",
            return_value=USER_AGENTS[0],
        ):
            stats = crawler.fetch_stats("org.telegram.messenger")

    assert stats["score"] == 4.5

    stats_fetcher.assert_called_once_with(
        "org.telegram.messenger",
        lang="en",
        country="us",
        headers={"User-Agent": USER_AGENTS[0]},
        proxy="http://proxy:8080",
    )


def test_fetch_reviews_passes_anti_blocking_options():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(2), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)

    with patch(
        "app.crawler.playstore.proxy_pool",
        iter(["http://proxy:8080"]),
    ):
        with patch.object(
            random,
            "choice",
            return_value=USER_AGENTS[0],
        ):
            result = crawler.fetch_reviews("org.telegram.messenger")

    assert len(result) == 2

    _, kwargs = reviews_fetcher.call_args
    assert kwargs["headers"] == {"User-Agent": USER_AGENTS[0]}
    assert kwargs["proxy"] == "http://proxy:8080"
    assert kwargs["count"] == MAX_REVIEWS


def test_fetch_reviews_limits_to_max():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(1500), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)

    result = crawler.fetch_reviews("org.telegram.messenger")

    assert len(result) == MAX_REVIEWS


def test_crawl_application_returns_stats_and_reviews():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(2), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)

    stats_message, review_messages = crawler.crawl_application(
        application_id=1,
        package_name="org.telegram.messenger",
    )

    assert stats_message["application_id"] == 1
    assert stats_message["package_name"] == "org.telegram.messenger"
    assert stats_message["data"]["score"] == 4.5
    assert "crawl_timestamp" in stats_message

    assert len(review_messages) == 2
    assert review_messages[0]["data"]["reviewId"] == "review-0"
    assert review_messages[0]["application_id"] == 1


def test_proxy_list_parsing_from_env(monkeypatch):
    import importlib

    monkeypatch.setenv(
        "PROXY_LIST",
        "http://p1:8080, http://p2:8080 ,http://p3:8080",
    )

    import app.crawler.playstore as playstore_module

    importlib.reload(playstore_module)

    assert playstore_module.PROXY_LIST == [
        "http://p1:8080",
        "http://p2:8080",
        "http://p3:8080",
    ]

    monkeypatch.delenv("PROXY_LIST", raising=False)
    importlib.reload(playstore_module)