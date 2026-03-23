from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.schemas.request import GeometryType, MeshType


class Bounds(BaseModel):
    """Bounds của mesh"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float


# ============== Geometry Responses ==============

class GeometryResponse(BaseModel):
    """Response geometry"""
    id: UUID
    name: str
    geometry_type: GeometryType
    # Rectangle
    x_min: Optional[float] = None
    y_min: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    # Circle
    center_x: Optional[float] = None
    center_y: Optional[float] = None
    radius: Optional[float] = None
    # Polygon
    points: Optional[List[List[float]]] = None
    closed: Optional[bool] = None
    # Computed
    bounds: Optional[Bounds] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Mesh Responses ==============

class MeshResponse(BaseModel):
    """Response mesh - format cho frontend"""
    id: UUID
    geometry_id: UUID
    mesh_type: MeshType
    name: str
    node_count: int
    element_count: int
    # Raw data cho frontend vẽ
    nodes: List[List[float]]  # n x 2
    elements: List[List[int]]  # m x 3 (triangle) hoặc m x 4 (quad)
    bounds: Bounds
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Health Check ==============

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    app_name: str
    version: str = "1.0.0"
