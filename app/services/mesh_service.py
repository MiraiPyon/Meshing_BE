import json
from datetime import datetime
from typing import List, Tuple, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.schemas.request import (
    RectangleCreate,
    CircleCreate,
    PolygonCreate,
    QuadMeshCreate,
    DelaunayMeshCreate,
)
from app.schemas.response import GeometryResponse, MeshResponse, Bounds
from app.engines.quad_engine import QuadMeshEngineFlexible
from app.engines.delaunay_engine import DelaunayMeshEngine
from app.database.models import Geometry as GeometryModel
from app.database.models import Mesh as MeshModel
from app.database.models import GeometryType as GeometryTypeEnum
from app.database.models import MeshType as MeshTypeEnum


class MeshService:
    """Service xử lý các nghiệp vụ liên quan đến Geometry và Mesh"""

    def __init__(self):
        self._quad_engine = QuadMeshEngineFlexible()
        self._delaunay_engine = DelaunayMeshEngine()

    # ============== Geometry Methods ==============

    def create_rectangle(self, db: Session, data: RectangleCreate) -> GeometryResponse:
        """Tạo hình chữ nhật"""
        x_max = data.x_min + data.width
        y_max = data.y_min + data.height

        geometry = GeometryModel(
            name=data.name,
            geometry_type=GeometryTypeEnum.RECTANGLE,
            x_min=data.x_min,
            y_min=data.y_min,
            width=data.width,
            height=data.height,
            bound_x_min=data.x_min,
            bound_x_max=x_max,
            bound_y_min=data.y_min,
            bound_y_max=y_max,
        )

        db.add(geometry)
        db.commit()
        db.refresh(geometry)

        return self._geometry_to_response(geometry)

    def create_circle(self, db: Session, data: CircleCreate) -> GeometryResponse:
        """Tạo hình tròn"""
        geometry = GeometryModel(
            name=data.name,
            geometry_type=GeometryTypeEnum.CIRCLE,
            center_x=data.center_x,
            center_y=data.center_y,
            radius=data.radius,
            bound_x_min=data.center_x - data.radius,
            bound_x_max=data.center_x + data.radius,
            bound_y_min=data.center_y - data.radius,
            bound_y_max=data.center_y + data.radius,
        )

        db.add(geometry)
        db.commit()
        db.refresh(geometry)

        return self._geometry_to_response(geometry)

    def create_polygon(self, db: Session, data: PolygonCreate) -> GeometryResponse:
        """Tạo hình tự do từ array các điểm"""
        x_coords = [p[0] for p in data.points]
        y_coords = [p[1] for p in data.points]

        geometry = GeometryModel(
            name=data.name,
            geometry_type=GeometryTypeEnum.POLYGON,
            points=json.dumps(data.points),
            closed=1 if data.closed else 0,
            bound_x_min=min(x_coords),
            bound_x_max=max(x_coords),
            bound_y_min=min(y_coords),
            bound_y_max=max(y_coords),
        )

        db.add(geometry)
        db.commit()
        db.refresh(geometry)

        return self._geometry_to_response(geometry)

    def get_geometry(self, db: Session, geometry_id: UUID) -> Optional[GeometryResponse]:
        """Lấy geometry theo ID"""
        geometry = db.query(GeometryModel).filter(GeometryModel.id == geometry_id).first()
        if geometry:
            return self._geometry_to_response(geometry)
        return None

    def list_geometries(self, db: Session) -> List[GeometryResponse]:
        """List tất cả geometries"""
        geometries = db.query(GeometryModel).all()
        return [self._geometry_to_response(g) for g in geometries]

    def delete_geometry(self, db: Session, geometry_id: UUID) -> bool:
        """Xóa geometry"""
        geometry = db.query(GeometryModel).filter(GeometryModel.id == geometry_id).first()
        if geometry:
            db.delete(geometry)
            db.commit()
            return True
        return False

    # ============== Mesh Methods ==============

    def create_quad_mesh(self, db: Session, data: QuadMeshCreate) -> MeshResponse:
        """Tạo lưới tứ giác"""
        # Lấy geometry
        geometry = db.query(GeometryModel).filter(GeometryModel.id == data.geometry_id).first()
        if not geometry:
            raise ValueError(f"Geometry {data.geometry_id} not found")

        # Chỉ hỗ trợ rectangle cho quad mesh
        if geometry.geometry_type != GeometryTypeEnum.RECTANGLE:
            raise ValueError("Quad mesh chỉ hỗ trợ hình chữ nhật")

        # Tạo mesh
        x_min = geometry.x_min
        y_min = geometry.y_min
        x_max = x_min + geometry.width
        y_max = y_min + geometry.height

        nodes, elements = self._quad_engine.generate_flexible(
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
            nx=data.nx,
            ny=data.ny,
        )

        mesh = MeshModel(
            geometry_id=data.geometry_id,
            mesh_type=MeshTypeEnum.QUAD,
            name=f"{geometry.name}_quad_{data.nx}x{data.ny}",
            node_count=len(nodes),
            element_count=len(elements),
            nodes=json.dumps(nodes),
            elements=json.dumps(elements),
        )

        db.add(mesh)
        db.commit()
        db.refresh(mesh)

        return self._mesh_to_response(db, mesh)

    def create_delaunay_mesh(self, db: Session, data: DelaunayMeshCreate) -> MeshResponse:
        """Tạo lưới tam giác Delaunay"""
        # Lấy geometry
        geometry = db.query(GeometryModel).filter(GeometryModel.id == data.geometry_id).first()
        if not geometry:
            raise ValueError(f"Geometry {data.geometry_id} not found")

        # Lấy boundary points
        if geometry.geometry_type == GeometryTypeEnum.RECTANGLE:
            x_min = geometry.x_min
            y_min = geometry.y_min
            x_max = x_min + geometry.width
            y_max = y_min + geometry.height

            boundary_points = [
                (x_min, y_min),
                (x_max, y_min),
                (x_max, y_max),
                (x_min, y_max),
            ]
        elif geometry.geometry_type == GeometryTypeEnum.CIRCLE:
            boundary_points = self._generate_circle_boundary(
                geometry.center_x,
                geometry.center_y,
                geometry.radius,
                resolution=32,
            )
        elif geometry.geometry_type == GeometryTypeEnum.POLYGON:
            points = json.loads(geometry.points)
            boundary_points = [tuple(p) for p in points]
        else:
            raise ValueError(f"Unsupported geometry type: {geometry.geometry_type}")

        # Tạo mesh
        nodes, elements = self._delaunay_engine.generate(
            points=boundary_points,
            resolution=20,
            max_area=data.max_area,
            min_angle=data.min_angle,
        )

        mesh = MeshModel(
            geometry_id=data.geometry_id,
            mesh_type=MeshTypeEnum.DELAUNAY,
            name=f"{geometry.name}_delaunay",
            node_count=len(nodes),
            element_count=len(elements),
            nodes=json.dumps(nodes),
            elements=json.dumps(elements),
        )

        db.add(mesh)
        db.commit()
        db.refresh(mesh)

        return self._mesh_to_response(db, mesh)

    def get_mesh(self, db: Session, mesh_id: UUID) -> Optional[MeshResponse]:
        """Lấy mesh theo ID"""
        mesh = db.query(MeshModel).filter(MeshModel.id == mesh_id).first()
        if mesh:
            return self._mesh_to_response(db, mesh)
        return None

    def list_meshes(self, db: Session) -> List[MeshResponse]:
        """List tất cả meshes"""
        meshes = db.query(MeshModel).all()
        return [self._mesh_to_response(db, m) for m in meshes]

    def delete_mesh(self, db: Session, mesh_id: UUID) -> bool:
        """Xóa mesh"""
        mesh = db.query(MeshModel).filter(MeshModel.id == mesh_id).first()
        if mesh:
            db.delete(mesh)
            db.commit()
            return True
        return False

    # ============== Helper Methods ==============

    def _geometry_to_response(self, geometry: GeometryModel) -> GeometryResponse:
        """Convert DB model to response"""
        bounds = Bounds(
            x_min=geometry.bound_x_min,
            x_max=geometry.bound_x_max,
            y_min=geometry.bound_y_min,
            y_max=geometry.bound_y_max,
        )

        points = None
        if geometry.points:
            points = json.loads(geometry.points)

        closed = None
        if geometry.closed is not None:
            closed = bool(geometry.closed)

        return GeometryResponse(
            id=geometry.id,
            name=geometry.name,
            geometry_type=geometry.geometry_type,
            x_min=geometry.x_min,
            y_min=geometry.y_min,
            width=geometry.width,
            height=geometry.height,
            center_x=geometry.center_x,
            center_y=geometry.center_y,
            radius=geometry.radius,
            points=points,
            closed=closed,
            bounds=bounds,
            created_at=geometry.created_at,
        )

    def _mesh_to_response(self, db: Session, mesh: MeshModel) -> MeshResponse:
        """Convert DB model to response"""
        geometry = db.query(GeometryModel).filter(GeometryModel.id == mesh.geometry_id).first()

        bounds = Bounds(
            x_min=geometry.bound_x_min,
            x_max=geometry.bound_x_max,
            y_min=geometry.bound_y_min,
            y_max=geometry.bound_y_max,
        )

        return MeshResponse(
            id=mesh.id,
            geometry_id=mesh.geometry_id,
            mesh_type=mesh.mesh_type,
            name=mesh.name,
            node_count=mesh.node_count,
            element_count=mesh.element_count,
            nodes=json.loads(mesh.nodes),
            elements=json.loads(mesh.elements),
            bounds=bounds,
            created_at=mesh.created_at,
        )

    def _generate_circle_boundary(
        self,
        cx: float,
        cy: float,
        radius: float,
        resolution: int = 32,
    ) -> List[Tuple[float, float]]:
        """Tạo các điểm boundary cho hình tròn"""
        import numpy as np

        theta = np.linspace(0, 2 * np.pi, resolution, endpoint=False)
        points = [
            (cx + radius * np.cos(t), cy + radius * np.sin(t))
            for t in theta
        ]
        return points


# Singleton instance
mesh_service = MeshService()
