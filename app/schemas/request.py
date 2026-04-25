from pydantic import BaseModel, Field
from typing import List, Tuple, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class GeometryType(str, Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
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


class PolygonCreate(BaseModel):
    """Request tạo hình tự do từ array các điểm"""
    name: str = "Polygon"
    points: List[List[float]] = Field(..., min_length=3, description="Array các điểm [x, y]")
    closed: bool = Field(default=True, description="True nếu polygon khép kín")


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
    min_angle: Optional[float] = Field(None, ge=20, le=33, description="Góc tối thiểu (độ)")


class MeshFromSketchCreate(BaseModel):
    """One-shot: tạo mesh từ sketch (outer loop + holes) không cần tạo geometry riêng"""
    name: str = Field(default="sketch", description="Tên lưới")
    outer_boundary: List[List[float]] = Field(..., min_length=3, description="Điểm biên ngoài [[x,y],...] ")
    holes: List[List[List[float]]] = Field(default_factory=list, description="Danh sách holes [[[x,y],...],...]")
    element_type: str = Field(default="delaunay", description="delaunay | quad")
    max_area: Optional[float] = Field(None, gt=0, description="Diện tích tối đa (Delaunay)")
    min_angle: Optional[float] = Field(None, ge=20, le=33, description="Góc tối thiểu (Delaunay)")
    nx: int = Field(10, ge=1, le=200, description="Số phần tử theo x (Quad)")
    ny: int = Field(10, ge=1, le=200, description="Số phần tử theo y (Quad)")
