import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.session import Base, engine, get_db
from app.core.deps import get_current_user
from app.database.models import User
import uuid

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
        with client.websocket_connect("/api/ws/dashboard") as websocket:
            pass
    except WebSocketDisconnect:
        pass
