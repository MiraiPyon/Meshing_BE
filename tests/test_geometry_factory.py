import pytest
from uuid import uuid4
from app.engines.geometry_factory import GeometryFactory
from app.schemas.request import RectangleCreate, CircleCreate, TriangleCreate, PolygonCreate
from app.database.models import GeometryType

def test_create_rectangle_from_factory():
    user_id = uuid4()
    req = RectangleCreate(name="rect", x_min=0, y_min=0, width=10, height=20)
    geo = GeometryFactory.create_geometry(req, user_id)

    assert geo.user_id == user_id
    assert geo.geometry_type == GeometryType.RECTANGLE
    assert geo.bound_x_max == 10
    assert geo.bound_y_max == 20

def test_create_circle_from_factory():
    user_id = uuid4()
    req = CircleCreate(name="circ", center_x=5, center_y=5, radius=3)
    geo = GeometryFactory.create_geometry(req, user_id)

    assert geo.user_id == user_id
    assert geo.geometry_type == GeometryType.CIRCLE
    assert geo.bound_x_min == 2
    assert geo.bound_x_max == 8
    assert geo.bound_y_max == 8

def test_create_polygon_from_factory():
    user_id = uuid4()
    req = PolygonCreate(name="poly", points=[[0,0], [1,0], [1,1]], closed=True)
    geo = GeometryFactory.create_geometry(req, user_id)

    assert geo.user_id == user_id
    assert geo.geometry_type == GeometryType.POLYGON
    assert geo.bound_x_max == 1
    assert geo.bound_y_max == 1
    assert geo.closed == 1

def test_create_triangle_from_factory():
    user_id = uuid4()
    req = TriangleCreate(name="tri", points=[[0, 0], [2, 0], [0, 1]])
    geo = GeometryFactory.create_geometry(req, user_id)

    assert geo.user_id == user_id
    assert geo.geometry_type == GeometryType.TRIANGLE
    assert geo.bound_x_max == 2
    assert geo.bound_y_max == 1
    assert geo.closed == 1

def test_invalid_factory_input():
    with pytest.raises(ValueError, match="Unsupported geometry creation request."):
        GeometryFactory.create_geometry({"invalid": "type"}, uuid4())
