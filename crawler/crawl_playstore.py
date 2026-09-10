from app.crawler.runner import run_crawler
from app.logging_config import setup_logging


setup_logging()


if __name__ == "__main__":
    run_crawler()