import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database.session import Base, get_db
from app.main import app


@pytest.fixture()
def api_client():
    sqlalchemy_database_url = "sqlite:///:memory:"
    test_engine = create_engine(
        sqlalchemy_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    current_user = {"id": uuid.uuid4()}

    def set_user(user_id):
        current_user["id"] = user_id

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return type("TestUser", (), {"id": current_user["id"]})()

    previous_db_override = app.dependency_overrides.get(get_db)
    previous_user_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    try:
        yield client, set_user
    finally:
        client.close()

        if previous_db_override is not None:
            app.dependency_overrides[get_db] = previous_db_override
        else:
            app.dependency_overrides.pop(get_db, None)

        if previous_user_override is not None:
            app.dependency_overrides[get_current_user] = previous_user_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


def _auth_headers():
    return {"Authorization": "Bearer fake"}


def test_project_snapshot_crud_round_trip(api_client):
    client, set_user = api_client
    user_id = uuid.uuid4()
    set_user(user_id)
    headers = _auth_headers()

    geo_resp = client.post(
        "/api/geometry/rectangle",
        json={"name": "ProjectRect", "x_min": 0, "y_min": 0, "width": 4, "height": 2},
        headers=headers,
    )
    assert geo_resp.status_code in (200, 201)
    geo_id = geo_resp.json()["id"]

    mesh_resp = client.post(
        "/api/mesh/quad",
        json={"geometry_id": geo_id, "nx": 4, "ny": 2},
        headers=headers,
    )
    assert mesh_resp.status_code in (200, 201)
    mesh_id = mesh_resp.json()["id"]

    create_resp = client.post(
        "/api/projects",
        json={
            "name": "Beam Study",
            "geometry_id": geo_id,
            "mesh_id": mesh_id,
            "element_type": "Q4",
            "meshing_params": {"strategy": "quad", "nx": 4, "ny": 2},
            "notes": "baseline snapshot",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_id = project["id"]
    assert project["name"] == "Beam Study"
    assert project["mesh_id"] == mesh_id

    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    assert any(item["id"] == project_id for item in list_resp.json())

    get_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["notes"] == "baseline snapshot"

    update_resp = client.put(
        f"/api/projects/{project_id}",
        json={"notes": "updated snapshot notes"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["notes"] == "updated snapshot notes"

    delete_resp = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert missing_resp.status_code == 404


def test_project_snapshot_ownership_isolation(api_client):
    client, set_user = api_client
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    headers = _auth_headers()

    set_user(user_a)
    create_resp = client.post(
        "/api/projects",
        json={"name": "User A Project", "notes": "private"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    set_user(user_b)
    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    assert all(item["id"] != project_id for item in list_resp.json())

    get_resp = client.get(f"/api/projects/{project_id}", headers=headers)
    assert get_resp.status_code == 404
