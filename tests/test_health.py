from fastapi.testclient import TestClient

from app.database.session import get_db
from app.main import app


client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_connected() -> None:
    class FakeSession:
        def execute(self, _query):
            return None

    def override_get_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}

    app.dependency_overrides.clear()


def test_database_health_disconnected() -> None:
    class FakeSession:
        def execute(self, _query):
            raise RuntimeError("database unavailable")

    def override_get_db():
        yield FakeSession()

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/health/db")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "disconnected"
    assert "database unavailable" in response.json()["reason"]

    app.dependency_overrides.clear()
