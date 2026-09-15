
import json
import logging
import time

from app import config
from app.logging_config import setup_logging
from app.metabase_client import MetabaseClient
from app.postgres import (
    apply_analytics_views,
    wait_for_postgres,
)
from app.questions import QUESTIONS


setup_logging()
logger = logging.getLogger("metabase-bootstrap")


def main() -> None:
    logger.info("Starting Metabase bootstrap")

    wait_for_postgres()
    apply_analytics_views()

    client = MetabaseClient()
    client.wait_for_ready()

    client.login()
    database_id = client.ensure_source_database()

    logger.info("Allowing Metabase time to register the new data source")
    time.sleep(3)

    card_ids_by_name = {
        question["name"]: client.create_or_update_question(database_id, question)
        for question in QUESTIONS
    }

    primary_card_ids = [
        card_ids_by_name[question["name"]]
        for question in QUESTIONS
        if question.get("dashboard") == "primary"
    ]

    secondary_card_ids = [
        card_ids_by_name[question["name"]]
        for question in QUESTIONS
        if question.get("dashboard") == "secondary"
    ]

    dashboard_id = client.provision_dashboard(primary_card_ids)

    logger.info(
        "Bootstrap complete: database_id=%s dashboard_id=%s "
        "questions_total=%s primary=%s secondary=%s",
        database_id,
        dashboard_id,
        len(card_ids_by_name),
        len(primary_card_ids),
        len(secondary_card_ids),
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "database_id": database_id,
                "dashboard_id": dashboard_id,
                "questions_total": len(card_ids_by_name),
                "questions_on_dashboard": len(primary_card_ids),
                "questions_off_dashboard": len(secondary_card_ids),
                "url": f"{config.MB_URL}/dashboard/{dashboard_id}",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()