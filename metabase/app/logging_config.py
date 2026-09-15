import logging
import os
import sys


def setup_logging(level: int = logging.INFO) -> None:
    env_level = os.getenv("LOG_LEVEL", "").upper()
    if env_level:
        level = getattr(logging, env_level, level)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )