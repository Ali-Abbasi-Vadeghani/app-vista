
import json
import logging
import os

import redis


logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

STATS_QUEUE = "playstore:stats"
REVIEWS_QUEUE = "playstore:reviews"
NETWORK_MEASUREMENTS_QUEUE = "network:measurements"

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
)


def dequeue_stats() -> dict | None:
    result = redis_client.lpop(STATS_QUEUE)
    if result is None:
        return None
    return json.loads(result)


def dequeue_reviews() -> dict | None:
    result = redis_client.lpop(REVIEWS_QUEUE)
    if result is None:
        return None
    return json.loads(result)


def dequeue_network_measurement() -> dict | None:
    result = redis_client.lpop(NETWORK_MEASUREMENTS_QUEUE)
    if result is None:
        return None
    return json.loads(result)


def check_redis_connection() -> bool:
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        logger.exception("Redis ping failed")
        return False


def get_queue_lengths() -> dict[str, int]:
    try:
        return {
            "stats": int(redis_client.llen(STATS_QUEUE)),
            "reviews": int(redis_client.llen(REVIEWS_QUEUE)),
            "network": int(redis_client.llen(NETWORK_MEASUREMENTS_QUEUE)),
        }
    except redis.RedisError:
        logger.exception("Failed to read queue lengths from Redis")
        return {}