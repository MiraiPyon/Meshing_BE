from fastapi.testclient import TestClient

import app.api.endpoints as endpoints
from app.main import app


client = TestClient(app)


def test_health_ok() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_connected(monkeypatch) -> None:
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query: str) -> None:
            assert query == "SELECT 1"

        def fetchone(self):
            return (1,)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    class FakePsycopg:
        @staticmethod
        def connect(**kwargs):
            assert kwargs["host"]
            assert kwargs["port"]
            assert kwargs["dbname"]
            assert kwargs["user"]
            return FakeConnection()

    monkeypatch.setattr(endpoints, "psycopg", FakePsycopg)

    response = client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_disconnected(monkeypatch) -> None:
    class FakePsycopg:
        @staticmethod
        def connect(**kwargs):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(endpoints, "psycopg", FakePsycopg)

    response = client.get("/api/v1/health/db")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"] == "disconnected"
    assert "database unavailable" in response.json()["reason"]


def test_database_health_without_psycopg(monkeypatch) -> None:
    monkeypatch.setattr(endpoints, "psycopg", None)

    response = client.get("/api/v1/health/db")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "database": "disconnected",
        "reason": "psycopg is not installed",
    }
