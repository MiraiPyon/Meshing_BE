from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.database.session import Base


class GeometryType(str, enum.Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    POLYGON = "polygon"


class MeshType(str, enum.Enum):
    QUAD = "quad"
    DELAUNAY = "delaunay"


class Geometry(Base):
    """Geometry model - lưu trữ hình học"""
    __tablename__ = "geometries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)

    # Type
    geometry_type = Column(Enum(GeometryType), nullable=False)

    # Rectangle
    x_min = Column(Float, nullable=True)
    y_min = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)

    # Circle
    center_x = Column(Float, nullable=True)
    center_y = Column(Float, nullable=True)
    radius = Column(Float, nullable=True)

    # Polygon - lưu dưới dạng JSON string
    points = Column(Text, nullable=True)  # JSON string of points
    closed = Column(Integer, nullable=True)  # 1 = True, 0 = False

    # Bounds
    bound_x_min = Column(Float, nullable=True)
    bound_x_max = Column(Float, nullable=True)
    bound_y_min = Column(Float, nullable=True)
    bound_y_max = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    meshes = relationship("Mesh", back_populates="geometry", cascade="all, delete-orphan")


class Mesh(Base):
    """Mesh model - lưu trữ kết quả meshing"""
    __tablename__ = "meshes"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geometry_id = Column(PGUUID(as_uuid=True), ForeignKey("geometries.id"), nullable=False)

    # Mesh info
    mesh_type = Column(Enum(MeshType), nullable=False)
    name = Column(String(255), nullable=False)

    # Counts
    node_count = Column(Integer, nullable=False)
    element_count = Column(Integer, nullable=False)

    # Data - lưu dưới dạng JSON string
    nodes = Column(Text, nullable=False)  # JSON string của [[x,y], ...]
    elements = Column(Text, nullable=False)  # JSON string của [[n1,n2,n3], ...]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    geometry = relationship("Geometry", back_populates="meshes")
