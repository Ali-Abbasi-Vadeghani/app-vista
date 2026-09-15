
from unittest.mock import patch

import pytest

from app import config
from app.metabase_client import MetabaseClient



def test_login_existing_instance(metabase_client, make_response):
    with patch("app.metabase_client.requests.post") as post_mock:
        post_mock.return_value = make_response(
            payload={"id": "session-abc"}
        )
        session_id = metabase_client.login()

    assert session_id == "session-abc"
    assert metabase_client.session_id == "session-abc"
    post_mock.assert_called_once()


def test_login_falls_back_to_setup(metabase_client, make_response):
    setup_response = make_response(payload={"id": "new-session"})

    with patch("app.metabase_client.requests.post") as post_mock:
        post_mock.side_effect = [
            make_response(status_code=401, text="unauthorized"),
            setup_response,
        ]
        session_id = metabase_client.login()

    assert session_id == "new-session"
    assert metabase_client.session_id == "new-session"


def test_login_recovers_from_concurrent_setup(metabase_client, make_response):
    with patch("app.metabase_client.requests.post") as post_mock:
        post_mock.side_effect = [
            make_response(status_code=401, text="unauthorized"),
            make_response(status_code=403, text="already setup"),
            make_response(payload={"id": "recovered-session"}),
        ]
        session_id = metabase_client.login()

    assert session_id == "recovered-session"



def test_ensure_source_database_existing(metabase_client):
    with patch.object(
        metabase_client,
        "list_databases",
        return_value=[{"id": 7, "name": config.MB_SOURCE_NAME}],
    ):
        db_id = metabase_client.ensure_source_database()

    assert db_id == 7


def test_ensure_source_database_creates_when_missing(
    metabase_client, make_response
):
    with patch.object(
        metabase_client, "list_databases", return_value=[]
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={"id": 42}),
    ) as request_mock:
        db_id = metabase_client.ensure_source_database()

    assert db_id == 42
    request_mock.assert_called_once()
    method, path = request_mock.call_args[0][:2]
    assert method == "POST"
    assert path == "/api/database"



def test_create_new_question(metabase_client, make_response):
    with patch.object(
        metabase_client, "list_cards", return_value=[]
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={"id": 100}),
    ) as request_mock:
        card_id = metabase_client.create_or_update_question(
            5,
            {"name": "New Q", "sql": "SELECT 1", "description": "d"},
        )

    assert card_id == 100
    method, path = request_mock.call_args[0][:2]
    assert method == "POST"
    assert path == "/api/card"


def test_update_existing_question(metabase_client, make_response):
    existing = [{"id": 55, "name": "Existing"}]

    with patch.object(
        metabase_client, "list_cards", return_value=existing
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={"id": 55}),
    ) as request_mock:
        card_id = metabase_client.create_or_update_question(
            5,
            {"name": "Existing", "sql": "SELECT 1", "description": "d"},
        )

    assert card_id == 55
    method, path = request_mock.call_args[0][:2]
    assert method == "PUT"
    assert path == "/api/card/55"



def test_next_negative_id_with_no_existing():
    assert MetabaseClient._next_negative_id([]) == -1


def test_next_negative_id_with_negatives():
    assert MetabaseClient._next_negative_id([1, 2, -1, -2, -3]) == -4



def test_build_dashboard_card_layout(metabase_client):
    card = metabase_client._build_dashboard_card(
        dashcard_id=10, card_id=20, position=0
    )
    assert card == {
        "id": 10,
        "card_id": 20,
        "row": 0,
        "col": 0,
        "size_x": 6,
        "size_y": 4,
    }






def test_provision_dashboard_creates_when_missing(
    metabase_client, make_response
):
    with patch.object(
        metabase_client, "_get_dashboard_by_name", return_value=None
    ), patch.object(
        metabase_client,
        "_get_dashboard_cards",
        return_value=[],
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={"id": 99}),
    ) as request_mock:
        dashboard_id = metabase_client.provision_dashboard([])

    assert dashboard_id == 99
    paths = [c[0][1] for c in request_mock.call_args_list]
    assert paths[0] == "/api/dashboard"
    assert paths[-1] == "/api/dashboard/99/cards"


def test_provision_dashboard_reuses_existing(
    metabase_client, make_response
):
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33, "name": config.MB_DASHBOARD_NAME},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=[]
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={}),
    ) as request_mock:
        dashboard_id = metabase_client.provision_dashboard([101, 102])

    assert dashboard_id == 33
    request_mock.assert_called_once()
    method, path = request_mock.call_args[0][:2]
    assert method == "PUT"
    assert path == "/api/dashboard/33/cards"


def test_provision_dashboard_adds_new_cards_with_negative_ids(
    metabase_client, make_response
):
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=[]
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={}),
    ) as request_mock:
        metabase_client.provision_dashboard([201, 202])

    payload = request_mock.call_args[1]["json"]
    cards = payload["cards"]
    assert len(cards) == 2
    assert cards[0]["card_id"] == 201
    assert cards[0]["id"] == -1
    assert cards[1]["card_id"] == 202
    assert cards[1]["id"] == -2


def test_provision_dashboard_removes_stale_cards(
    metabase_client, make_response
):
    existing = [
        {"id": 500, "card_id": 900},
        {"id": 501, "card_id": 901},
    ]
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=existing
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={}),
    ) as request_mock:
        metabase_client.provision_dashboard([900])

    payload = request_mock.call_args[1]["json"]
    cards = payload["cards"]

    kept = [c for c in cards if c["card_id"] == 900]
    removed = [c for c in cards if c["card_id"] is None]

    assert len(kept) == 1
    assert kept[0]["id"] == 500

    assert len(removed) == 1
    assert removed[0]["id"] == 501


def test_provision_dashboard_keeps_existing_positions(
    metabase_client, make_response
):
    existing = [
        {"id": 700, "card_id": 10},
        {"id": 701, "card_id": 11},
    ]
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=existing
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={}),
    ) as request_mock:
        metabase_client.provision_dashboard([11, 10])

    payload = request_mock.call_args[1]["json"]
    cards = {c["card_id"]: c for c in payload["cards"]}

    assert cards[11]["row"] == 0
    assert cards[11]["col"] == 0
    assert cards[10]["row"] == 0
    assert cards[10]["col"] == 6


def test_provision_dashboard_adds_negative_id_below_existing(
    metabase_client, make_response
):
    existing = [{"id": -5, "card_id": 800}]
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=existing
    ), patch.object(
        metabase_client,
        "_request",
        return_value=make_response(payload={}),
    ) as request_mock:
        metabase_client.provision_dashboard([800, 801])

    payload = request_mock.call_args[1]["json"]
    cards = {c["card_id"]: c for c in payload["cards"]}
    assert cards[801]["id"] == -6


def test_provision_dashboard_handles_request_error(
    metabase_client, make_response
):
    with patch.object(
        metabase_client,
        "_get_dashboard_by_name",
        return_value={"id": 33},
    ), patch.object(
        metabase_client, "_get_dashboard_cards", return_value=[]
    ), patch.object(
        metabase_client,
        "_request",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError):
            metabase_client.provision_dashboard([1])



def test_request_raises_on_4xx(metabase_client, make_response):
    with patch(
        "app.metabase_client.requests.request",
        return_value=make_response(status_code=500, text="server error"),
    ):
        with pytest.raises(RuntimeError) as exc:
            metabase_client._request("GET", "/api/anything")

    assert "500" in str(exc.value)





def test_wait_for_ready_succeeds_immediately(metabase_client, make_response):
    with patch(
        "app.metabase_client.requests.get",
        return_value=make_response(payload={}),
    ):
        metabase_client.wait_for_ready()


def test_wait_for_ready_raises_after_attempts(metabase_client, make_response):
    with patch(
        "app.metabase_client.requests.get",
        return_value=make_response(status_code=503, payload={}),
    ), patch("app.metabase_client.time.sleep", return_value=None):
        with pytest.raises(RuntimeError):
            metabase_client.wait_for_ready(attempts=3, delay=0)