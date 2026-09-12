from app.consumer import run_consumer
from app.logging_config import setup_logging


setup_logging()


if __name__ == "__main__":
    run_consumer()