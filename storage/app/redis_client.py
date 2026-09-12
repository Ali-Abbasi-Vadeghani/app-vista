import json
import os

import redis


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

STATS_QUEUE = "playstore:stats"
REVIEWS_QUEUE = "playstore:reviews"


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


def check_redis_connection() -> bool:
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False