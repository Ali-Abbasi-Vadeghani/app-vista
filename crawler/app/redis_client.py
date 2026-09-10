
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import redis
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


logger = logging.getLogger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

STATS_QUEUE = "playstore:stats"
REVIEWS_QUEUE = "playstore:reviews"


redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def check_redis_connection() -> bool:
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False


def _build_message(data: dict) -> dict:
    return {
        "message_id": str(uuid.uuid4()),
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }


@retry(
    retry=retry_if_exception_type(redis.RedisError),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _rpush(queue_name: str, payload: str) -> None:
    redis_client.rpush(queue_name, payload)


def _publish(queue_name: str, data: dict) -> None:
    message = _build_message(data)
    payload = json.dumps(message, ensure_ascii=False, default=str)
    _rpush(queue_name, payload)


def publish_stats(data: dict) -> None:
    _publish(STATS_QUEUE, data)


def publish_reviews(data: dict) -> None:
    _publish(REVIEWS_QUEUE, data)


def get_queue_length(queue_name: str) -> int:
    return int(redis_client.llen(queue_name))