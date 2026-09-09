import json
import os

import redis


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)

PLAYSTORE_STATS_QUEUE = "playstore:stats"

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


def push_playstore_stats(data: dict) -> None:
    redis_client.rpush(
        PLAYSTORE_STATS_QUEUE,
        json.dumps(
            data,
            ensure_ascii=False,
        ),
    )


def get_redis_connection() -> redis.Redis:
    return redis_client