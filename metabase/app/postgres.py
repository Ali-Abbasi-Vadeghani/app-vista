
import logging
import time
from pathlib import Path

import psycopg

from app import config


logger = logging.getLogger(__name__)


def wait_for_postgres(timeout_attempts: int = 60, delay: int = 2) -> None:
    logger.info(
        "Waiting for PostgreSQL at %s:%s/%s",
        config.PG_HOST,
        config.PG_PORT,
        config.APP_DB,
    )

    for attempt in range(timeout_attempts):
        try:
            with psycopg.connect(
                host=config.PG_HOST,
                port=config.PG_PORT,
                user=config.PG_USER,
                password=config.PG_PASSWORD,
                dbname=config.APP_DB,
                autocommit=True,
            ) as conn:
                conn.execute("SELECT 1")
                logger.info("PostgreSQL is ready")
                return
        except Exception:
            logger.debug("PostgreSQL not ready yet (attempt %s)", attempt + 1)
            time.sleep(delay)

    raise RuntimeError("PostgreSQL did not become ready in time")


def apply_analytics_views() -> None:
    sql_path = Path(config.SQL_FILE)

    if not sql_path.exists():
        raise RuntimeError(f"Analytics SQL file not found: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")

    logger.info("Applying analytics views from %s", sql_path)

    with psycopg.connect(
        host=config.PG_HOST,
        port=config.PG_PORT,
        user=config.PG_USER,
        password=config.PG_PASSWORD,
        dbname=config.APP_DB,
    ) as conn:
        conn.execute(sql)
        conn.commit()

    logger.info("Analytics views applied")