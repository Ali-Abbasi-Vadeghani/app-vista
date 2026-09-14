
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

NETWORK_MEASUREMENTS_QUEUE = "network:measurements"


redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def check_redis_connection() -> bool:
    try:
        return bool(redis_client.ping())
    except redis.RedisError:
        return False


def _build_message(data: dict) -> tuple[str, dict]:
    message_id = str(uuid.uuid4())
    message = {
        "message_id": message_id,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    return message_id, message


@retry(
    retry=retry_if_exception_type(redis.RedisError),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _rpush(queue_name: str, payload: str) -> None:
    redis_client.rpush(queue_name, payload)


def publish_network_measurement(data: dict) -> str:
    message_id, message = _build_message(data)
    payload = json.dumps(message, ensure_ascii=False, default=str)

    logger.info(
        "Publishing network measurement package=%s scenario=%s message_id=%s",
        data.get("package_name"),
        data.get("scenario"),
        message_id,
    )

    _rpush(NETWORK_MEASUREMENTS_QUEUE, payload)

    logger.info(
        "Network measurement published package=%s scenario=%s message_id=%s",
        data.get("package_name"),
        data.get("scenario"),
        message_id,
    )

    return message_id