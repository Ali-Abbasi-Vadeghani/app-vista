# tests/test_applications.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app


TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


Base.metadata.create_all(
    bind=test_engine
)


def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def clear_database():
    Base.metadata.drop_all(
        bind=test_engine
    )

    Base.metadata.create_all(
        bind=test_engine
    )


def setup_function():
    clear_database()


def application_payload():
    return {
        "name": "Telegram",
        "package_name": "org.telegram.messenger",
        "category": "Social",
    }


def test_create_application():
    response = client.post(
        "/applications",
        json=application_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] == 1
    assert data["name"] == "Telegram"
    assert data["package_name"] == "org.telegram.messenger"
    assert data["category"] == "Social"
    assert data["is_active"] is True
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_create_application_with_empty_name():
    payload = application_payload()
    payload["name"] = ""

    response = client.post(
        "/applications",
        json=payload,
    )

    assert response.status_code == 422


def test_create_application_with_whitespace_name():
    payload = application_payload()
    payload["name"] = "   "

    response = client.post(
        "/applications",
        json=payload,
    )

    assert response.status_code == 422


def test_create_duplicate_application():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.post(
        "/applications",
        json=application_payload(),
    )

    assert response.status_code == 409

    data = response.json()

    assert (
        data["detail"]
        == "Application with this package_name already exists"
    )


def test_get_applications():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.get(
        "/applications"
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Telegram"


def test_get_application():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.get(
        "/applications/1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["name"] == "Telegram"


def test_get_application_not_found():
    response = client.get(
        "/applications/999"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Application not found"


def test_update_application():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.put(
        "/applications/1",
        json={
            "name": "Telegram Messenger",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["name"] == "Telegram Messenger"
    assert data["category"] == "Messaging"
    assert data["is_active"] is True


def test_update_application_not_found():
    response = client.put(
        "/applications/999",
        json={
            "name": "Something",
            "package_name": "com.example.something",
            "category": "Test",
        },
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Application not found"


def test_update_application_with_duplicate_package_name():
    client.post(
        "/applications",
        json=application_payload(),
    )

    client.post(
        "/applications",
        json={
            "name": "WhatsApp",
            "package_name": "com.whatsapp",
            "category": "Messaging",
        },
    )

    response = client.put(
        "/applications/2",
        json={
            "name": "WhatsApp",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )

    assert response.status_code == 409


def test_update_application_with_empty_name():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.put(
        "/applications/1",
        json={
            "name": "",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )

    assert response.status_code == 422


def test_delete_application():
    client.post(
        "/applications",
        json=application_payload(),
    )

    response = client.delete(
        "/applications/1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert data["is_active"] is False


def test_delete_application_not_found():
    response = client.delete(
        "/applications/999"
    )

    assert response.status_code == 404

    data = response.json()

    assert data["detail"] == "Application not found"


def test_deactivated_application_remains_in_database():
    client.post(
        "/applications",
        json=application_payload(),
    )

    client.delete(
        "/applications/1"
    )

    response = client.get(
        "/applications/1"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["is_active"] is False