
def test_root_endpoint(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_application(api_client, payload):
    response = api_client.post("/applications", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Telegram"
    assert data["package_name"] == "org.telegram.messenger"
    assert data["category"] == "Social"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data


def test_create_application_strips_whitespace(api_client):
    response = api_client.post(
        "/applications",
        json={
            "name": "  Telegram  ",
            "package_name": "  org.telegram.messenger  ",
            "category": "  Social  ",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Telegram"
    assert data["package_name"] == "org.telegram.messenger"
    assert data["category"] == "Social"


def test_create_application_with_empty_name(api_client, payload):
    body = {**payload, "name": ""}
    assert api_client.post("/applications", json=body).status_code == 422


def test_create_application_with_blank_name(api_client, payload):
    body = {**payload, "name": "   "}
    assert api_client.post("/applications", json=body).status_code == 422


def test_create_application_with_empty_package(api_client, payload):
    body = {**payload, "package_name": ""}
    assert api_client.post("/applications", json=body).status_code == 422


def test_create_application_with_empty_category(api_client, payload):
    body = {**payload, "category": ""}
    assert api_client.post("/applications", json=body).status_code == 422


def test_create_duplicate_application(api_client, payload):
    api_client.post("/applications", json=payload)
    response = api_client.post("/applications", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_create_application_with_missing_field(api_client):
    response = api_client.post(
        "/applications",
        json={"name": "Telegram"},
    )
    assert response.status_code == 422


def test_get_applications_empty(api_client):
    response = api_client.get("/applications")
    assert response.status_code == 200
    assert response.json() == []


def test_get_applications(api_client, create_application):
    create_application()
    response = api_client.get("/applications")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_applications_returns_sorted_by_id(api_client, create_application):
    create_application(name="A", package_name="com.a")
    create_application(name="B", package_name="com.b")
    create_application(name="C", package_name="com.c")

    response = api_client.get("/applications")
    ids = [item["id"] for item in response.json()]
    assert ids == sorted(ids)


def test_get_applications_active_only(api_client, create_application):
    create_application(name="A", package_name="com.a")
    create_application(name="B", package_name="com.b")

    api_client.delete("/applications/1")

    response = api_client.get("/applications", params={"active": "true"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["package_name"] == "com.b"


def test_get_application_by_id(api_client, create_application):
    create_application()
    response = api_client.get("/applications/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_application_not_found(api_client):
    response = api_client.get("/applications/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_update_application(api_client, create_application):
    create_application()
    response = api_client.put(
        "/applications/1",
        json={
            "name": "Telegram Messenger",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Telegram Messenger"
    assert data["category"] == "Messaging"


def test_update_application_package_conflict(api_client, create_application):
    create_application(name="A", package_name="com.a")
    create_application(name="B", package_name="com.b")

    response = api_client.put(
        "/applications/2",
        json={
            "name": "B renamed",
            "package_name": "com.a",
            "category": "Social",
        },
    )
    assert response.status_code == 409


def test_update_application_not_found(api_client, payload):
    response = api_client.put("/applications/999", json=payload)
    assert response.status_code == 404


def test_update_inactive_application(api_client, create_application, payload):
    create_application()
    api_client.delete("/applications/1")

    response = api_client.put(
        "/applications/1",
        json={
            "name": "Telegram Updated",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )
    assert response.status_code == 400
    assert "inactive" in response.json()["detail"]


def test_delete_application_soft_deletes(api_client, create_application):
    create_application()
    response = api_client.delete("/applications/1")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_delete_application_not_found(api_client):
    response = api_client.delete("/applications/999")
    assert response.status_code == 404


def test_delete_is_idempotent(api_client, create_application):
    create_application()
    first = api_client.delete("/applications/1")
    second = api_client.delete("/applications/1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is False