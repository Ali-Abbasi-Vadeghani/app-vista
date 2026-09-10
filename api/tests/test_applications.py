import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def payload():
    return {
        "name": "Telegram",
        "package_name": "org.telegram.messenger",
        "category": "Social",
    }


def test_create_application():
    response = client.post("/applications", json=payload())
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Telegram"
    assert data["is_active"] is True


def test_create_application_with_empty_name():
    body = payload()
    body["name"] = ""
    assert client.post("/applications", json=body).status_code == 422


def test_create_duplicate_application():
    client.post("/applications", json=payload())
    response = client.post("/applications", json=payload())
    assert response.status_code == 409


def test_get_applications():
    client.post("/applications", json=payload())
    response = client.get("/applications")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_application_not_found():
    assert client.get("/applications/999").status_code == 404


def test_update_application():
    client.post("/applications", json=payload())
    response = client.put(
        "/applications/1",
        json={
            "name": "Telegram Messenger",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Telegram Messenger"


def test_update_inactive_application():
    client.post("/applications", json=payload())
    client.delete("/applications/1")
    response = client.put(
        "/applications/1",
        json={
            "name": "Telegram Updated",
            "package_name": "org.telegram.messenger",
            "category": "Messaging",
        },
    )
    assert response.status_code == 400


def test_delete_application_soft_deletes():
    client.post("/applications", json=payload())
    response = client.delete("/applications/1")
    assert response.status_code == 200
    assert response.json()["is_active"] is False