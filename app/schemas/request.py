from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

SQRT_TWO = 2 ** 0.5


class GeometryType(str, Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    POLYGON = "polygon"


class MeshType(str, Enum):
    QUAD = "quad"
    DELAUNAY = "delaunay"


# ============== Geometry Requests ==============

class RectangleCreate(BaseModel):
    """Request tạo hình chữ nhật"""
    name: str = "Rectangle"
    x_min: float = Field(..., description="Tọa độ x góc dưới trái")
    y_min: float = Field(..., description="Tọa độ y góc dưới trái")
    width: float = Field(..., gt=0, description="Chiều rộng")
    height: float = Field(..., gt=0, description="Chiều cao")


class CircleCreate(BaseModel):
    """Request tạo hình tròn"""
    name: str = "Circle"
    center_x: float = Field(..., description="Tọa độ x tâm")
    center_y: float = Field(..., description="Tọa độ y tâm")
    radius: float = Field(..., gt=0, description="Bán kính")


class TriangleCreate(BaseModel):
    """Request tạo hình tam giác từ đúng 3 điểm."""
    name: str = "Triangle"
    points: List[List[float]] = Field(..., min_length=3, max_length=3, description="3 điểm [x, y]")

    @field_validator("points")
    @classmethod
    def _validate_points(cls, value: List[List[float]]) -> List[List[float]]:
        for p in value:
            if len(p) != 2:
                raise ValueError("Each triangle point must have exactly 2 coordinates")
        return value


class PolygonCreate(BaseModel):
    """Request tạo hình tự do từ array các điểm"""
    name: str = "Polygon"
    points: List[List[float]] = Field(..., min_length=3, description="Array các điểm [x, y]")
    closed: bool = Field(default=True, description="True nếu polygon khép kín")

    @field_validator("points")
    @classmethod
    def _validate_points(cls, value: List[List[float]]) -> List[List[float]]:
        for p in value:
            if len(p) != 2:
                raise ValueError("Each polygon point must have exactly 2 coordinates")
        return value


# ============== Mesh Requests ==============

class QuadMeshCreate(BaseModel):
    """Request tạo lưới tứ giác"""
    geometry_id: UUID
    nx: int = Field(10, ge=1, le=100, description="Số phần tử theo trục x")
    ny: int = Field(10, ge=1, le=100, description="Số phần tử theo trục y")


class DelaunayMeshCreate(BaseModel):
    """Request tạo lưới tam giác Delaunay"""
    geometry_id: UUID
    max_area: Optional[float] = Field(None, gt=0, description="Diện tích tối đa mỗi tam giác")
    min_angle: Optional[float] = Field(
        20.0,
        ge=20.0,
        le=60,
        description="Góc tối thiểu (độ), mặc định 20.0",
    )
    max_edge_length: Optional[float] = Field(
        None,
        gt=0,
        description="Độ dài cạnh tối đa cho refinement",
    )
    max_circumradius_ratio: Optional[float] = Field(
        1.01,
        gt=1,
        le=2.0,
        description="Ngưỡng r/l tối đa, mặc định 1.01",
    )
    max_refine_iterations: int = Field(0, ge=0, le=100, description="Số vòng refinement tối đa")
    smoothing_iterations: int = Field(0, ge=0, le=20, description="Số vòng Laplacian smoothing")
    adaptive_size_field: bool = Field(False, description="Bật local adaptive mesh size field")
    adaptive_min_edge_factor: float = Field(
        0.45,
        ge=0.2,
        le=1.0,
        description="Tỉ lệ cạnh nhỏ nhất gần biên khi adaptive size field bật",
    )
    adaptive_influence_radius_factor: float = Field(
        0.25,
        ge=0.01,
        le=2.0,
        description="Bán kính ảnh hưởng adaptive theo tỉ lệ bbox diagonal",
    )


class GeometryComponentCreate(BaseModel):
    """One disconnected polygon component with optional holes."""

    outer_boundary: List[List[float]] = Field(..., min_length=3, description="Outer loop [[x,y],...]")
    holes: List[List[List[float]]] = Field(default_factory=list, description="Hole loops [[[x,y],...],...]")

    @field_validator("outer_boundary")
    @classmethod
    def _validate_component_outer(cls, value: List[List[float]]) -> List[List[float]]:
        for p in value:
            if len(p) != 2:
                raise ValueError("Each component boundary point must contain exactly 2 coordinates")
        return value

    @field_validator("holes")
    @classmethod
    def _validate_component_holes(cls, value: List[List[List[float]]]) -> List[List[List[float]]]:
        for hole in value:
            if len(hole) < 3:
                raise ValueError("Each component hole must contain at least 3 points")
            for p in hole:
                if len(p) != 2:
                    raise ValueError("Each component hole point must contain exactly 2 coordinates")
        return value


class MeshFromSketchCreate(BaseModel):
    """One-shot: tạo mesh từ sketch (outer loop + holes) không cần tạo geometry riêng"""
    name: str = Field(default="sketch", description="Tên lưới")
    outer_boundary: List[List[float]] = Field(..., min_length=3, description="Điểm biên ngoài [[x,y],...] ")
    holes: List[List[List[float]]] = Field(default_factory=list, description="Danh sách holes [[[x,y],...],...]")
    components: Optional[List[GeometryComponentCreate]] = Field(
        default=None,
        description="Optional disconnected components; when present, these drive meshing",
    )
    element_type: str = Field(default="delaunay", description="delaunay | quad")
    max_area: Optional[float] = Field(None, gt=0, description="Diện tích tối đa (Delaunay)")
    min_angle: Optional[float] = Field(20.0, ge=20.0, le=60, description="Góc tối thiểu (Delaunay)")
    max_edge_length: Optional[float] = Field(
        None,
        gt=0,
        description="Độ dài cạnh tối đa cho refinement (Delaunay)",
    )
    max_circumradius_ratio: Optional[float] = Field(
        1.01,
        gt=1,
        le=2.0,
        description="Ngưỡng r/l tối đa, mặc định 1.01",
    )
    max_refine_iterations: int = Field(0, ge=0, le=100, description="Số vòng refinement tối đa")
    smoothing_iterations: int = Field(0, ge=0, le=20, description="Số vòng Laplacian smoothing")
    adaptive_size_field: bool = Field(False, description="Bật local adaptive mesh size field")
    adaptive_min_edge_factor: float = Field(0.45, ge=0.2, le=1.0, description="Tỉ lệ cạnh nhỏ nhất gần biên")
    adaptive_influence_radius_factor: float = Field(0.25, ge=0.01, le=2.0, description="Bán kính ảnh hưởng adaptive")
    nx: int = Field(10, ge=1, le=200, description="Số phần tử theo x (Quad)")
    ny: int = Field(10, ge=1, le=200, description="Số phần tử theo y (Quad)")

    @field_validator("outer_boundary")
    @classmethod
    def _validate_outer_boundary(cls, value: List[List[float]]) -> List[List[float]]:
        for p in value:
            if len(p) != 2:
                raise ValueError("Each boundary point must contain exactly 2 coordinates")
        return value

    @model_validator(mode="after")
    def _validate_holes_and_element_type(self):
        etype = self.element_type.strip().lower()
        if etype not in {"delaunay", "quad"}:
            raise ValueError("element_type must be either 'delaunay' or 'quad'")

        for hole in self.holes:
            if len(hole) < 3:
                raise ValueError("Each hole must contain at least 3 points")
            for p in hole:
                if len(p) != 2:
                    raise ValueError("Each hole point must contain exactly 2 coordinates")
        return self


class ShapeDatMeshCreate(BaseModel):
    """Request tạo mesh từ nội dung file shape.dat."""

    name: str = Field(default="shape_dat", description="Tên lưới")
    shape_dat: str = Field(..., min_length=3, description="Nội dung file shape.dat")
    element_type: str = Field(default="delaunay", description="delaunay | quad")
    max_area: Optional[float] = Field(None, gt=0, description="Diện tích tối đa mỗi tam giác")
    min_angle: Optional[float] = Field(20.0, ge=20.0, le=60, description="Góc tối thiểu")
    max_edge_length: Optional[float] = Field(None, gt=0, description="Độ dài cạnh tối đa")
    max_circumradius_ratio: Optional[float] = Field(1.01, gt=1, le=2.0, description="Ngưỡng r/l tối đa")
    max_refine_iterations: int = Field(0, ge=0, le=100, description="Số vòng refinement tối đa")
    smoothing_iterations: int = Field(0, ge=0, le=20, description="Số vòng Laplacian smoothing")
    adaptive_size_field: bool = Field(False, description="Bật local adaptive mesh size field")
    adaptive_min_edge_factor: float = Field(0.45, ge=0.2, le=1.0, description="Tỉ lệ cạnh nhỏ nhất gần biên")
    adaptive_influence_radius_factor: float = Field(0.25, ge=0.01, le=2.0, description="Bán kính ảnh hưởng adaptive")
    nx: int = Field(10, ge=1, le=200, description="Số phần tử theo x (Quad)")
    ny: int = Field(10, ge=1, le=200, description="Số phần tử theo y (Quad)")

    @field_validator("element_type")
    @classmethod
    def _validate_element_type(cls, value: str) -> str:
        etype = value.strip().lower()
        if etype not in {"delaunay", "quad"}:
            raise ValueError("element_type must be either 'delaunay' or 'quad'")
        return etype


class BooleanOperationRequest(BaseModel):
    """Request thực hiện boolean operation (union / subtract / intersect) trên 2 polygon."""
    polygon_a: List[List[float]] = Field(..., min_length=3, description="Polygon A [[x,y], ...]")
    polygon_b: List[List[float]] = Field(..., min_length=3, description="Polygon B [[x,y], ...]")
    operation: str = Field(..., description="union | subtract | intersect")
    name: str = Field(default="boolean_result", description="Tên kết quả")

    @field_validator("operation")
    @classmethod
    def _validate_operation(cls, value: str) -> str:
        op = value.strip().lower()
        if op not in {"union", "subtract", "intersect"}:
            raise ValueError("operation must be one of: union, subtract, intersect")
        return op


# ============== Project Snapshot Requests ==============

class ProjectCreate(BaseModel):
    """Create project snapshot."""

    name: str = Field(..., min_length=1, max_length=255)
    geometry_id: Optional[UUID] = None
    mesh_id: Optional[UUID] = None
    element_type: Optional[str] = Field(
        default=None,
        description="Element type tag, e.g. T3 or Q4",
    )
    meshing_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Persisted meshing params for project restore",
    )
    notes: Optional[str] = Field(default=None, max_length=5000)


class ProjectUpdate(BaseModel):
    """Update project snapshot (partial update)."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    geometry_id: Optional[UUID] = None
    mesh_id: Optional[UUID] = None
    element_type: Optional[str] = Field(
        default=None,
        description="Element type tag, e.g. T3 or Q4",
    )
    meshing_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Persisted meshing params for project restore",
    )
    notes: Optional[str] = Field(default=None, max_length=5000)
