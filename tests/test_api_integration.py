import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import Base, get_db
from app.core.deps import get_current_user
from app.database.models import User
import io
import json
import threading
import uuid
import zipfile

# Setup an in-memory SQLite DB for integration tests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

fake_user = User(id=uuid.uuid4(), email="test@example.com")
def override_get_current_user():
    return fake_user

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

@pytest.fixture(scope="module")
def auth_token():
    return "fake_token"

def test_geometry_creation(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Create Rectangle
    resp = client.post("/api/geometry/rectangle", json={
        "name": "Rect1", "x_min": 0, "y_min": 0, "width": 10, "height": 10
    }, headers=headers)
    assert resp.status_code in (200, 201)
    assert resp.json()["geometry_type"] == "rectangle"

    resp = client.post("/api/geometry/triangle", json={
        "name": "Tri1", "points": [[0, 0], [2, 0], [0, 1]]
    }, headers=headers)
    assert resp.status_code in (200, 201)
    assert resp.json()["geometry_type"] == "triangle"
    assert len(resp.json()["points"]) == 3

def test_mesh_creation(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Create Geometry
    geo_resp = client.post("/api/geometry/rectangle", json={
        "name": "Rect1", "x_min": 0, "y_min": 0, "width": 10, "height": 10
    }, headers=headers)
    geo_id = geo_resp.json()["id"]

    # Create Quad Mesh
    resp = client.post("/api/mesh/quad", json={
        "geometry_id": geo_id,
        "nx": 2,
        "ny": 2
    }, headers=headers)
    assert resp.status_code in (200, 201)
    assert resp.json()["mesh_type"] == "quad"

def test_fea_solve(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Create Geometry
    geo_resp = client.post("/api/geometry/rectangle", json={
        "name": "Rect1", "x_min": 0, "y_min": 0, "width": 10, "height": 10
    }, headers=headers)
    geo_id = geo_resp.json()["id"]

    # Create Quad Mesh
    mesh_resp = client.post("/api/mesh/quad", json={
        "geometry_id": geo_id,
        "nx": 2,
        "ny": 2
    }, headers=headers)
    mesh_id = mesh_resp.json()["id"]

    # Solve FEA
    resp = client.post("/api/fea/solve", json={
        "mesh_id": mesh_id,
        "material": {"E": 2e11, "nu": 0.3, "thickness": 0.1, "density": 7800},
        "analysis_type": "plane_stress",
        "boundary_conditions": [{"node_id": 1, "dof": "ux", "value": 0.0}]
    }, headers=headers)
    assert resp.status_code in (200, 201)
    assert "result" in resp.json()
    assert "displacements" in resp.json()["result"]

def test_websocket_connection():
    from starlette.websockets import WebSocketDisconnect
    try:
        with client.websocket_connect("/api/ws/dashboard"):
            pass
    except WebSocketDisconnect:
        pass


def test_observer_event_from_sync_mesh_endpoint(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    with client.websocket_connect("/api/ws/dashboard") as ws:
        timer = threading.Timer(2.0, lambda: ws.close())
        timer.start()
        try:
            geo_resp = client.post("/api/geometry/rectangle", json={
                "name": "ObsRect", "x_min": 0, "y_min": 0, "width": 2, "height": 1
            }, headers=headers)
            geo_id = geo_resp.json()["id"]

            client.post("/api/mesh/quad", json={
                "geometry_id": geo_id,
                "nx": 2,
                "ny": 1
            }, headers=headers)

            msg = ws.receive_text()
            payload = json.loads(msg)
            assert payload["event"] == "mesh_created"
            assert "mesh_id" in payload["data"]
        finally:
            timer.cancel()


def test_boolean_endpoint_returns_components_for_multipolygon(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = client.post(
        "/api/geometry/boolean",
        json={
            "polygon_a": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "polygon_b": [[3, 0], [4, 0], [4, 1], [3, 1]],
            "operation": "union",
            "name": "disjoint_union",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_multipolygon"] is True
    assert data["component_count"] == 2
    assert abs(data["total_area"] - 2.0) < 1e-9
    assert len(data["components"]) == 2
    assert "outer_boundary" in data  # backward-compatible field


def test_export_csv_zip_contains_nodes_and_elements(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}

    geo_resp = client.post("/api/geometry/rectangle", json={
        "name": "ZipRect", "x_min": 0, "y_min": 0, "width": 2, "height": 1
    }, headers=headers)
    geo_id = geo_resp.json()["id"]

    mesh_resp = client.post("/api/mesh/quad", json={
        "geometry_id": geo_id,
        "nx": 2,
        "ny": 1
    }, headers=headers)
    mesh_id = mesh_resp.json()["id"]
    node_count = mesh_resp.json()["node_count"]
    element_count = mesh_resp.json()["element_count"]

    resp = client.get(f"/api/mesh/{mesh_id}/export?format=csv_zip", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(resp.content), "r") as archive:
        names = set(archive.namelist())
        assert "nodes.csv" in names
        assert "elements.csv" in names

        nodes_csv = archive.read("nodes.csv").decode("utf-8").strip().splitlines()
        elems_csv = archive.read("elements.csv").decode("utf-8").strip().splitlines()
        assert len(nodes_csv) == node_count + 1
        assert len(elems_csv) == element_count + 1


def test_export_csv_contains_nodes_and_elements(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}

    geo_resp = client.post("/api/geometry/rectangle", json={
        "name": "LegacyRect", "x_min": 0, "y_min": 0, "width": 1, "height": 1
    }, headers=headers)
    geo_id = geo_resp.json()["id"]
    mesh_resp = client.post("/api/mesh/quad", json={
        "geometry_id": geo_id,
        "nx": 1,
        "ny": 1
    }, headers=headers)
    mesh_id = mesh_resp.json()["id"]

    resp = client.get(f"/api/mesh/{mesh_id}/export?format=csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    csv_text = resp.text
    assert "section,id,x,y" in csv_text.splitlines()[0]
    assert "node,1," in csv_text
    assert "element,1," in csv_text


def test_quad_sketch_endpoint_rejects_holes_and_non_rectangle(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}

    with_hole = client.post(
        "/api/mesh/from-sketch",
        json={
            "name": "bad_quad_hole",
            "outer_boundary": [[0, 0], [4, 0], [4, 3], [0, 3]],
            "holes": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
            "element_type": "quad",
            "nx": 4,
            "ny": 3,
        },
        headers=headers,
    )
    assert with_hole.status_code == 400
    assert "no holes" in with_hole.json()["detail"]

    non_rect = client.post(
        "/api/mesh/from-sketch",
        json={
            "name": "bad_quad_shape",
            "outer_boundary": [[0, 0], [4, 0], [3, 2], [0, 3]],
            "holes": [],
            "element_type": "quad",
            "nx": 4,
            "ny": 3,
        },
        headers=headers,
    )
    assert non_rect.status_code == 400
    assert "axis-aligned rectangular" in non_rect.json()["detail"]
