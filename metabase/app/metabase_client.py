
import logging
import time

import requests

from app import config


logger = logging.getLogger(__name__)


class MetabaseClient:
    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = (base_url or config.MB_URL).rstrip("/")
        self.timeout = timeout
        self.session_id = None

    def _request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {}) or {}
        if self.session_id:
            headers["X-Metabase-Session"] = self.session_id

        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Metabase API {method} {path} -> {response.status_code}: "
                f"{response.text[:1000]}"
            )

        return response

    def wait_for_ready(self, attempts: int = 120, delay: int = 2) -> None:
        logger.info("Waiting for Metabase at %s", self.base_url)

        for _ in range(attempts):
            try:
                response = requests.get(
                    f"{self.base_url}/api/health", timeout=3
                )
                if response.ok:
                    logger.info("Metabase is ready")
                    return
            except requests.RequestException:
                pass
            time.sleep(delay)

        raise RuntimeError("Metabase did not become ready in time")

    def login(self) -> str:
        logger.info("Attempting to log in as %s", config.MB_ADMIN_EMAIL)

        response = requests.post(
            f"{self.base_url}/api/session",
            json={
                "username": config.MB_ADMIN_EMAIL,
                "password": config.MB_ADMIN_PASSWORD,
            },
            timeout=self.timeout,
        )

        if response.ok:
            self.session_id = response.json()["id"]
            logger.info("Logged in successfully")
            return self.session_id

        logger.info("Login failed; attempting to create a new Metabase instance")

        return self._create_instance()

    def _create_instance(self) -> str:
        try:
            props_response = requests.get(
                f"{self.base_url}/api/session/properties",
                timeout=self.timeout,
            )
            props = props_response.json()
            setup_token = props.get("setup-token")
        except requests.RequestException:
            setup_token = None

        payload = {
            "token": setup_token,
            "user": {
                "email": config.MB_ADMIN_EMAIL,
                "first_name": config.MB_ADMIN_FIRST_NAME,
                "last_name": config.MB_ADMIN_LAST_NAME,
                "password": config.MB_ADMIN_PASSWORD,
                "site_name": config.MB_SITE_NAME,
            },
            "prefs": {"site_name": config.MB_SITE_NAME},
        }

        response = requests.post(
            f"{self.base_url}/api/setup", json=payload, timeout=self.timeout
        )

        if response.ok:
            self.session_id = response.json()["id"]
            logger.info("New Metabase instance created")
            return self.session_id

        logger.info("Setup failed; retrying login (concurrent bootstrap)")
        
        response = requests.post(
            f"{self.base_url}/api/session",
            json={
                "username": config.MB_ADMIN_EMAIL,
                "password": config.MB_ADMIN_PASSWORD,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.session_id = response.json()["id"]
        return self.session_id


    def list_databases(self) -> list[dict]:
        response = self._request("GET", "/api/database")
        body = response.json()
        if isinstance(body, dict):
            return body.get("data", [])
        return body

    def ensure_source_database(self) -> int:
        for db in self.list_databases():
            if db.get("name") == config.MB_SOURCE_NAME:
                logger.info(
                    "Source database '%s' already configured (id=%s)",
                    config.MB_SOURCE_NAME,
                    db["id"],
                )
                return db["id"]

        logger.info("Creating source database connection '%s'", config.MB_SOURCE_NAME)

        payload = {
            "engine": "postgres",
            "name": config.MB_SOURCE_NAME,
            "details": {
                "host": config.PG_HOST,
                "port": config.PG_PORT,
                "dbname": config.APP_DB,
                "user": config.PG_USER,
                "password": config.PG_PASSWORD,
            },
        }

        response = self._request("POST", "/api/database", json=payload)
        database_id = response.json()["id"]
        logger.info("Created source database connection (id=%s)", database_id)
        return database_id

    def list_cards(self) -> list[dict]:
        response = self._request("GET", "/api/card")
        body = response.json()
        if isinstance(body, dict):
            return body.get("data", [])
        return body

    def create_or_update_question(self, database_id: int, question: dict) -> int:
        existing = self.list_cards()
        card = next(
            (c for c in existing if c.get("name") == question["name"]),
            None,
        )

        payload = {
            "name": question["name"],
            "description": question.get("description", ""),
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": question["sql"],
                    "template-tags": {},
                },
                "database": database_id,
            },
            "display": question.get("display", "table"),
            "visualization_settings": question.get("visualization_settings", {}),
        }

        if card:
            if card.get("result_metadata"):
                payload["result_metadata"] = card["result_metadata"]

            self._request("PUT", f"/api/card/{card['id']}", json=payload)
            logger.info("Updated question '%s' (id=%s)", question["name"], card["id"])
            return card["id"]

        response = self._request("POST", "/api/card", json=payload)
        card_id = response.json()["id"]
        logger.info("Created question '%s' (id=%s)", question["name"], card_id)
        return card_id

    def _get_dashboard_by_name(self, name: str) -> dict | None:
        response = self._request("GET", "/api/dashboard")
        body = response.json()
        items = body.get("data", []) if isinstance(body, dict) else body
        return next((d for d in items if d.get("name") == name), None)

    def _get_dashboard_cards(self, dashboard_id: int) -> list[dict]:
        response = self._request("GET", f"/api/dashboard/{dashboard_id}")
        return response.json().get("dashcards", [])

    @staticmethod
    def _next_negative_id(existing_ids: list[int]) -> int:
        negatives = [i for i in existing_ids if i is not None and i < 0]
        return (min(negatives) - 1) if negatives else -1

    def _build_dashboard_card(
        self,
        dashcard_id: int,
        card_id: int,
        position: int,
    ) -> dict:
        return {
            "id": dashcard_id,
            "card_id": card_id,
            "row": (position // 2) * 4,
            "col": (position % 2) * 6,
            "size_x": 6,
            "size_y": 4,
        }

    def provision_dashboard(self, desired_card_ids: list[int]) -> int:
        dashboard = self._get_dashboard_by_name(config.MB_DASHBOARD_NAME)

        if dashboard:
            dashboard_id = dashboard["id"]
            logger.info("Dashboard already exists (id=%s)", dashboard_id)
        else:
            response = self._request(
                "POST",
                "/api/dashboard",
                json={
                    "name": config.MB_DASHBOARD_NAME,
                    "description": (
                        "Application performance, reviews, installs and network quality. "
                        "Note: network_risk_index is a project-level composite for ranking "
                        "only; it has no independent physical meaning."
                    ),
                },
            )
            dashboard_id = response.json()["id"]
            logger.info("Created dashboard (id=%s)", dashboard_id)

        existing_cards = self._get_dashboard_cards(dashboard_id)
        existing_by_card_id = {
            c.get("card_id"): c
            for c in existing_cards
            if c.get("card_id") is not None
        }
        existing_dashcard_ids = [
            c.get("id") for c in existing_cards if c.get("id") is not None
        ]

        desired_set = set(desired_card_ids)
        existing_set = set(existing_by_card_id.keys())

        kept: list[dict] = []
        added_count = 0
        removed_count = 0

        for position, card_id in enumerate(desired_card_ids):
            if card_id in existing_by_card_id:
                current_dashcard = existing_by_card_id[card_id]
                kept.append(
                    self._build_dashboard_card(
                        dashcard_id=current_dashcard["id"],
                        card_id=card_id,
                        position=position,
                    )
                )

        next_negative_id = self._next_negative_id(existing_dashcard_ids)
        for position, card_id in enumerate(desired_card_ids):
            if card_id in existing_by_card_id:
                continue
            kept.append(
                self._build_dashboard_card(
                    dashcard_id=next_negative_id,
                    card_id=card_id,
                    position=position,
                )
            )
            next_negative_id -= 1
            added_count += 1

        for stale_card_id in existing_set - desired_set:
            stale_dashcard = existing_by_card_id[stale_card_id]
            kept.append(
                {
                    "id": stale_dashcard["id"],
                    "card_id": None,
                }
            )
            removed_count += 1

        logger.info(
            "Reconciling dashboard cards: kept=%s added=%s removed=%s",
            len(kept) - added_count - removed_count,
            added_count,
            removed_count,
        )

        self._request(
            "PUT",
            f"/api/dashboard/{dashboard_id}/cards",
            json={"cards": kept},
        )

        return dashboard_id