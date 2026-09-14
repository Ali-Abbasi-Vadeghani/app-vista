
from app.logging_config import setup_logging

setup_logging()

from app.consumer import run_consumer


if __name__ == "__main__":
    run_consumer()