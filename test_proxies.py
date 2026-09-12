

import concurrent.futures
import logging
import time

import httpx


logger = logging.getLogger(__name__)


TEST_URL = "https://httpbin.org/ip"
TIMEOUT_SECONDS = 8
MAX_WORKERS = 20


def load_proxies_from_file(filepath: str = "http.txt") -> list[str]:
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


def test_proxy(proxy: str) -> dict:
    start = time.monotonic()

    try:
        response = httpx.get(
            TEST_URL,
            proxy=proxy,
            timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=TIMEOUT_SECONDS),
        )
        elapsed = time.monotonic() - start

        if response.status_code == 200:
            return {
                "proxy": proxy,
                "ok": True,
                "time": round(elapsed, 2),
            }

        return {"proxy": proxy, "ok": False, "time": round(elapsed, 2)}

    except Exception:
        return {"proxy": proxy, "ok": False, "time": None}


def test_proxies(proxies: list[str]) -> list[str]:
    if not proxies:
        return []

    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_proxy, p): p for p in proxies}

        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    working = [r for r in results if r["ok"]]
    working.sort(key=lambda r: r["time"])  

    return [r["proxy"] for r in working]


def get_healthy_proxies(filepath: str = "http.txt") -> list[str]:
    proxies = load_proxies_from_file(filepath)

    if not proxies:
        logger.info("No proxies found in %s", filepath)
        return []

    logger.info("Testing %s proxies from %s", len(proxies), filepath)

    healthy = test_proxies(proxies)

    logger.info(
        "Found %s healthy proxies out of %s",
        len(healthy),
        len(proxies),
    )

    return healthy


def main() -> None:
    healthy = get_healthy_proxies()

    if healthy:
        print("\n📋 Healthy proxies:\n")
        for p in healthy:
            print(f"  ✅ {p}")

        print("\n" + "=" * 60)
        print("📋 For docker-compose.yml:\n")
        print(f'PROXY_LIST: "{",".join(healthy)}"')
        print("=" * 60)
    else:
        print("⚠️  No healthy proxies found.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()