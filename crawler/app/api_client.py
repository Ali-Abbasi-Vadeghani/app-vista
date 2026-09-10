

import logging
import os

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError


logger = logging.getLogger(__name__)


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "10"))


class ApplicationSummary(BaseModel):

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    package_name: str
    category: str
    is_active: bool


def fetch_active_applications() -> list[ApplicationSummary]:

    url = f"{API_BASE_URL}/applications"
    params = {"active": "true"}

    logger.info("Fetching active applications from %s", url)

    with httpx.Client(timeout=API_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)

    response.raise_for_status()

    payload = response.json()

    try:
        applications = [
            ApplicationSummary.model_validate(item) for item in payload
        ]
    except ValidationError:
        logger.exception("API returned an unexpected payload shape")
        raise

    logger.info(
        "Fetched %s active applications from the API",
        len(applications),
    )

    return applications