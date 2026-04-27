from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
import enum

from app.database.session import Base


def utcnow():
    return datetime.now(timezone.utc)


# ============== Auth ==============

class User(Base):
    """User model - lưu trữ tài khoản người dùng"""
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    picture = Column(String(512), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    geometries = relationship("Geometry", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("ProjectSnapshot", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """Refresh token model - lưu trữ refresh tokens"""
    __tablename__ = "refresh_tokens"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


# ============== Enums ==============

class GeometryType(str, enum.Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    POLYGON = "polygon"


class MeshType(str, enum.Enum):
    QUAD = "quad"
    DELAUNAY = "delaunay"


# ============== Meshing ==============

class Geometry(Base):
    """Geometry model - lưu trữ hình học"""
    __tablename__ = "geometries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
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

    # Polygon
    points = Column(Text, nullable=True)
    closed = Column(Integer, nullable=True)

    # Bounds
    bound_x_min = Column(Float, nullable=True)
    bound_x_max = Column(Float, nullable=True)
    bound_y_min = Column(Float, nullable=True)
    bound_y_max = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="geometries")
    meshes = relationship("Mesh", back_populates="geometry", cascade="all, delete-orphan")


class Mesh(Base):
    """Mesh model - lưu trữ kết quả meshing"""
    __tablename__ = "meshes"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geometry_id = Column(PGUUID(as_uuid=True), ForeignKey("geometries.id"), nullable=False)
    mesh_type = Column(Enum(MeshType), nullable=False)
    name = Column(String(255), nullable=False)
    node_count = Column(Integer, nullable=False)
    element_count = Column(Integer, nullable=False)
    nodes = Column(Text, nullable=False)
    elements = Column(Text, nullable=False)
    meshing_params = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    geometry = relationship("Geometry", back_populates="meshes")


class ProjectSnapshot(Base):
    """Project snapshot model - lưu trạng thái project để tái sử dụng."""
    __tablename__ = "project_snapshots"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    geometry_id = Column(PGUUID(as_uuid=True), ForeignKey("geometries.id", ondelete="SET NULL"), nullable=True)
    mesh_id = Column(PGUUID(as_uuid=True), ForeignKey("meshes.id", ondelete="SET NULL"), nullable=True)
    element_type = Column(String(16), nullable=True)
    meshing_params = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="projects")
