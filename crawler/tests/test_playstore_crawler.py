from unittest.mock import Mock, patch

import pytest

from app.crawler.playstore import (
    MAX_REVIEWS,
    PLAYSTORE_COUNTRY,
    PLAYSTORE_LANGUAGE,
    EmptyReviewsError,
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


def test_max_reviews_constant():
    assert MAX_REVIEWS == 1000


def test_playstore_language_and_country():
    assert PLAYSTORE_LANGUAGE == "en"
    assert PLAYSTORE_COUNTRY == "us"


def test_crawler_initializes_with_fetchers():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(1), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)

    assert crawler.stats_fetcher is stats_fetcher
    assert crawler.reviews_fetcher is reviews_fetcher


def test_fetch_stats_calls_fetcher_with_lang_country():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    stats = crawler.fetch_stats("org.telegram.messenger")

    assert stats["score"] == 4.5
    stats_fetcher.assert_called_once_with(
        "org.telegram.messenger",
        lang="en",
        country="us",
    )


def test_fetch_stats_uses_proxy_when_available():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = ["http://proxy1:8080"]

    with patch.object(
        crawler, "_install_proxy"
    ) as install_mock:
        crawler.fetch_stats("org.telegram.messenger")

    install_mock.assert_called_once_with("http://proxy1:8080")


def test_fetch_stats_no_proxy_when_none_healthy():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    with patch.object(crawler, "_install_proxy") as install_mock:
        crawler.fetch_stats("org.telegram.messenger")

    install_mock.assert_not_called()


def test_fetch_reviews_returns_list():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(2), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    result = crawler.fetch_reviews("org.telegram.messenger")

    assert len(result) == 2
    assert result[0]["reviewId"] == "review-0"


def test_fetch_reviews_passes_sort_and_count():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(2), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    crawler.fetch_reviews("org.telegram.messenger")

    _, kwargs = reviews_fetcher.call_args
    assert kwargs["count"] == MAX_REVIEWS
    assert kwargs["lang"] == "en"
    assert kwargs["country"] == "us"


def test_fetch_reviews_raises_when_empty():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    with pytest.raises(EmptyReviewsError):
        crawler.fetch_reviews("org.telegram.messenger")


def test_fetch_reviews_limits_to_max():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(1500), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    result = crawler.fetch_reviews("org.telegram.messenger")

    assert len(result) == MAX_REVIEWS


def test_crawl_application_returns_stats_and_reviews():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(2), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

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


def test_crawl_application_stats_message_contains_all_fields():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=(_fake_reviews(1), None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    stats_message, _ = crawler.crawl_application(
        application_id=1,
        package_name="org.telegram.messenger",
    )

    data = stats_message["data"]
    assert data["minInstalls"] == 1000000
    assert data["score"] == 4.5
    assert data["ratings"] == 50000
    assert data["reviews"] == 10000
    assert data["updated"] == 1700000000
    assert data["version"] == "1.0.0"
    assert data["adSupported"] is True


def test_get_random_proxy_returns_none_when_empty():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = []

    assert crawler._get_random_proxy() is None


def test_get_random_proxy_returns_from_list():
    stats_fetcher = Mock(return_value=_fake_stats())
    reviews_fetcher = Mock(return_value=([], None))

    crawler = PlayStoreCrawler(stats_fetcher, reviews_fetcher)
    crawler.healthy_proxies = ["http://p1:8080", "http://p2:8080"]

    proxy = crawler._get_random_proxy()
    assert proxy in crawler.healthy_proxies