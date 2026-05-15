from pydantic import BaseModel, ConfigDict
from typing import Any, Dict, List, Optional
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
    components: Optional[List[dict]] = None
    closed: Optional[bool] = None
    # Computed
    bounds: Optional[Bounds] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Mesh Responses ==============

class MeshResponse(BaseModel):
    """Response mesh - format cho frontend"""
    id: UUID
    mesh_id: UUID  # Backward-compatible alias for clients reading mesh_id
    geometry_id: UUID
    mesh_type: MeshType
    name: str
    node_count: int
    element_count: int
    # Raw data cho frontend vẽ
    nodes: List[List[float]]  # n x 2
    elements: List[List[int]]  # m x 3 (triangle) hoặc m x 4 (quad), always 0-based
    element_type: Optional[str] = None  # T3 or Q4
    dof_total: Optional[int] = None
    dashboard: Optional[dict] = None
    pslg: Optional[dict] = None
    connectivity_matrices: Optional[dict] = None
    meshing_params: Optional[Dict[str, Any]] = None
    bounds: Bounds
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


