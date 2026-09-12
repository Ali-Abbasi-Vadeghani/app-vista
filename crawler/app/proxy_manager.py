
import concurrent.futures
import logging
import time

import httpx


logger = logging.getLogger(__name__)


TEST_URL = "https://httpbin.org/ip"
TIMEOUT_SECONDS = 8
MAX_WORKERS = 20


def load_proxies_from_file(filepath: str) -> list[str]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.warning("Proxy file %s not found", filepath)
        return []

    proxies = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("http://") and not line.startswith("https://"):
            line = f"http://{line}"
        proxies.append(line)

    return proxies


def test_proxy(proxy: str) -> bool:
    try:
        response = httpx.get(
            TEST_URL,
            proxy=proxy,
            timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=TIMEOUT_SECONDS),
        )
        return response.status_code == 200
    except Exception:
        return False


def get_healthy_proxies(filepath: str) -> list[str]:
    proxies = load_proxies_from_file(filepath)

    if not proxies:
        logger.info("No proxies found in %s", filepath)
        return []

    logger.info("Testing %s proxies from %s...", len(proxies), filepath)

    healthy = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxies}

        for future in concurrent.futures.as_completed(futures):
            proxy = futures[future]
            if future.result():
                healthy.append(proxy)

    logger.info("Found %s healthy proxies out of %s", len(healthy), len(proxies))

    return healthy