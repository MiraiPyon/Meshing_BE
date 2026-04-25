"""
Mesh Service — CRUD cho Geometry và Mesh, mỗi user chỉ thấy data của mình.
"""

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
    MeshFromSketchCreate,
)
from app.schemas.response import GeometryResponse, MeshResponse, Bounds
from app.engines.quad_engine import QuadMeshEngineFlexible
from app.engines.delaunay_engine import DelaunayMeshEngine, DelaunayMeshEngineWithHoles
from app.database.models import Geometry as GeometryModel
from app.database.models import Mesh as MeshModel
from app.database.models import GeometryType as GeometryTypeEnum
from app.database.models import MeshType as MeshTypeEnum


class MeshService:
    """Service xử lý Geometry và Mesh — mỗi user chỉ truy cập data của mình."""

    def __init__(self):
        self._quad_engine = QuadMeshEngineFlexible()
        self._delaunay_engine = DelaunayMeshEngine()
        self._delaunay_holes_engine = DelaunayMeshEngineWithHoles()

    # ============== Geometry Methods ==============

    def create_rectangle(self, db: Session, data: RectangleCreate, user_id: UUID) -> GeometryResponse:
        x_max = data.x_min + data.width
        y_max = data.y_min + data.height

        geometry = GeometryModel(
            user_id=user_id,
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

    def create_circle(self, db: Session, data: CircleCreate, user_id: UUID) -> GeometryResponse:
        geometry = GeometryModel(
            user_id=user_id,
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

    def create_polygon(self, db: Session, data: PolygonCreate, user_id: UUID) -> GeometryResponse:
        x_coords = [p[0] for p in data.points]
        y_coords = [p[1] for p in data.points]

        geometry = GeometryModel(
            user_id=user_id,
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

    def get_geometry(self, db: Session, geometry_id: UUID, user_id: UUID) -> Optional[GeometryResponse]:
        geometry = db.query(GeometryModel).filter(
            GeometryModel.id == geometry_id,
            GeometryModel.user_id == user_id,
        ).first()
        if geometry:
            return self._geometry_to_response(geometry)
        return None

    def list_geometries(self, db: Session, user_id: UUID) -> List[GeometryResponse]:
        geometries = db.query(GeometryModel).filter(GeometryModel.user_id == user_id).all()
        return [self._geometry_to_response(g) for g in geometries]

    def delete_geometry(self, db: Session, geometry_id: UUID, user_id: UUID) -> bool:
        geometry = db.query(GeometryModel).filter(
            GeometryModel.id == geometry_id,
            GeometryModel.user_id == user_id,
        ).first()
        if geometry:
            db.delete(geometry)
            db.commit()
            return True
        return False

    # ============== Mesh Methods ==============

    def create_quad_mesh(self, db: Session, data: QuadMeshCreate, user_id: UUID) -> MeshResponse:
        geometry = db.query(GeometryModel).filter(
            GeometryModel.id == data.geometry_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not geometry:
            raise ValueError(f"Geometry {data.geometry_id} not found")

        if geometry.geometry_type != GeometryTypeEnum.RECTANGLE:
            raise ValueError("Quad mesh chỉ hỗ trợ hình chữ nhật")

        x_min = geometry.x_min
        y_min = geometry.y_min
        x_max = x_min + geometry.width
        y_max = y_min + geometry.height

        nodes, elements = self._quad_engine.generate_flexible(
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            nx=data.nx, ny=data.ny,
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

    def create_delaunay_mesh(self, db: Session, data: DelaunayMeshCreate, user_id: UUID) -> MeshResponse:
        geometry = db.query(GeometryModel).filter(
            GeometryModel.id == data.geometry_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not geometry:
            raise ValueError(f"Geometry {data.geometry_id} not found")

        if geometry.geometry_type == GeometryTypeEnum.RECTANGLE:
            boundary_points = [
                (geometry.x_min, geometry.y_min),
                (geometry.x_min + geometry.width, geometry.y_min),
                (geometry.x_min + geometry.width, geometry.y_min + geometry.height),
                (geometry.x_min, geometry.y_min + geometry.height),
            ]
        elif geometry.geometry_type == GeometryTypeEnum.CIRCLE:
            boundary_points = self._generate_circle_boundary(
                geometry.center_x, geometry.center_y, geometry.radius, resolution=32,
            )
        elif geometry.geometry_type == GeometryTypeEnum.POLYGON:
            boundary_points = [tuple(p) for p in json.loads(geometry.points)]
        else:
            raise ValueError(f"Unsupported geometry type: {geometry.geometry_type}")

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

    def get_mesh(self, db: Session, mesh_id: UUID, user_id: UUID) -> Optional[MeshResponse]:
        mesh = db.query(MeshModel).join(GeometryModel).filter(
            MeshModel.id == mesh_id,
            GeometryModel.user_id == user_id,
        ).first()
        if mesh:
            return self._mesh_to_response(db, mesh)
        return None

    def list_meshes(self, db: Session, user_id: UUID) -> List[MeshResponse]:
        meshes = db.query(MeshModel).join(GeometryModel).filter(
            GeometryModel.user_id == user_id,
        ).all()
        return [self._mesh_to_response(db, m) for m in meshes]

    def delete_mesh(self, db: Session, mesh_id: UUID, user_id: UUID) -> bool:
        mesh = db.query(MeshModel).join(GeometryModel).filter(
            MeshModel.id == mesh_id,
            GeometryModel.user_id == user_id,
        ).first()
        if mesh:
            db.delete(mesh)
            db.commit()
            return True
        return False

    def create_mesh_from_sketch(
        self, db: Session, data: MeshFromSketchCreate, user_id: UUID,
    ) -> MeshResponse:
        """One-shot: lưu geometry + tạo mesh từ sketch (outer+holes)."""
        outer = [tuple(p) for p in data.outer_boundary]
        holes = [[tuple(p) for p in loop] for loop in data.holes]

        # Compute bounds
        xs = [p[0] for p in outer]
        ys = [p[1] for p in outer]
        all_points_combined = json.dumps({
            "outer": data.outer_boundary,
            "holes": data.holes,
        })

        geometry = GeometryModel(
            user_id=user_id,
            name=data.name,
            geometry_type=GeometryTypeEnum.POLYGON,
            points=all_points_combined,
            closed=1,
            bound_x_min=min(xs), bound_x_max=max(xs),
            bound_y_min=min(ys), bound_y_max=max(ys),
        )
        db.add(geometry)
        db.commit()
        db.refresh(geometry)

        if data.element_type == "quad":
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            nodes, elements = self._quad_engine.generate_flexible(
                x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                nx=data.nx, ny=data.ny,
            )
            mesh_type = MeshTypeEnum.QUAD
            mesh_name = f"{data.name}_quad_{data.nx}x{data.ny}"
        else:
            if holes:
                nodes, elements = self._delaunay_holes_engine.generate_with_holes(
                    outer_boundary=outer,
                    holes=holes,
                    resolution=20,
                )
            else:
                nodes, elements = self._delaunay_engine.generate(
                    points=outer,
                    resolution=20,
                    max_area=data.max_area,
                    min_angle=data.min_angle,
                )
            mesh_type = MeshTypeEnum.DELAUNAY
            mesh_name = f"{data.name}_delaunay"

        mesh = MeshModel(
            geometry_id=geometry.id,
            mesh_type=mesh_type,
            name=mesh_name,
            node_count=len(nodes),
            element_count=len(elements),
            nodes=json.dumps(nodes),
            elements=json.dumps(elements),
        )
        db.add(mesh)
        db.commit()
        db.refresh(mesh)
        return self._mesh_to_response(db, mesh)

    def export_mesh(self, db: Session, mesh_id: UUID, user_id: UUID, fmt: str) -> dict:
        """Export mesh sang json/dat/csv."""
        mesh = db.query(MeshModel).join(GeometryModel).filter(
            MeshModel.id == mesh_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not mesh:
            raise ValueError(f"Mesh {mesh_id} not found")

        nodes = json.loads(mesh.nodes)
        elements = json.loads(mesh.elements)

        if fmt == "json":
            return {
                "format": "json",
                "content_type": "application/json",
                "filename": f"{mesh.name}.json",
                "data": {"nodes": nodes, "elements": elements,
                         "node_count": mesh.node_count, "element_count": mesh.element_count},
            }

        if fmt == "dat":
            lines = [f"# Mesh: {mesh.name}",
                     f"# Nodes: {mesh.node_count}  Elements: {mesh.element_count}",
                     "NODES", f"{mesh.node_count}"]
            for i, (x, y) in enumerate(nodes, 1):
                lines.append(f"{i:6d}  {x:14.8f}  {y:14.8f}")
            lines.append("ELEMENTS")
            lines.append(f"{mesh.element_count}")
            for i, elem in enumerate(elements, 1):
                node_str = "  ".join(f"{n:6d}" for n in elem)
                lines.append(f"{i:6d}  {node_str}")
            return {
                "format": "dat",
                "content_type": "text/plain",
                "filename": f"{mesh.name}.dat",
                "data": "\n".join(lines),
            }

        if fmt == "csv":
            node_lines = ["id,x,y"]
            for i, (x, y) in enumerate(nodes, 1):
                node_lines.append(f"{i},{x},{y}")
            elem_lines = ["id," + ",".join(f"n{j+1}" for j in range(len(elements[0]))) if elements else "id"]
            for i, elem in enumerate(elements, 1):
                elem_lines.append(f"{i}," + ",".join(str(n) for n in elem))
            return {
                "format": "csv",
                "content_type": "text/csv",
                "filename": f"{mesh.name}_nodes.csv",
                "data": {"nodes": "\n".join(node_lines), "elements": "\n".join(elem_lines)},
            }

        raise ValueError(f"Unknown format: {fmt}. Supported: json, dat, csv")

    # ============== Helper Methods ==============

    def _geometry_to_response(self, geometry: GeometryModel) -> GeometryResponse:
        bounds = Bounds(
            x_min=geometry.bound_x_min, x_max=geometry.bound_x_max,
            y_min=geometry.bound_y_min, y_max=geometry.bound_y_max,
        )
        points = json.loads(geometry.points) if geometry.points else None
        closed = bool(geometry.closed) if geometry.closed is not None else None

        return GeometryResponse(
            id=geometry.id, name=geometry.name,
            geometry_type=geometry.geometry_type,
            x_min=geometry.x_min, y_min=geometry.y_min,
            width=geometry.width, height=geometry.height,
            center_x=geometry.center_x, center_y=geometry.center_y,
            radius=geometry.radius,
            points=points, closed=closed,
            bounds=bounds, created_at=geometry.created_at,
        )

    def _mesh_to_response(self, db: Session, mesh: MeshModel) -> MeshResponse:
        geometry = db.query(GeometryModel).filter(GeometryModel.id == mesh.geometry_id).first()
        bounds = Bounds(
            x_min=geometry.bound_x_min, x_max=geometry.bound_x_max,
            y_min=geometry.bound_y_min, y_max=geometry.bound_y_max,
        )

        return MeshResponse(
            id=mesh.id, geometry_id=mesh.geometry_id,
            mesh_type=mesh.mesh_type, name=mesh.name,
            node_count=mesh.node_count, element_count=mesh.element_count,
            nodes=json.loads(mesh.nodes), elements=json.loads(mesh.elements),
            bounds=bounds, created_at=mesh.created_at,
        )

    @staticmethod
    def _generate_circle_boundary(
        cx: float, cy: float, radius: float, resolution: int = 32,
    ) -> List[Tuple[float, float]]:
        import numpy as np
        theta = np.linspace(0, 2 * np.pi, resolution, endpoint=False)
        return [(cx + radius * np.cos(t), cy + radius * np.sin(t)) for t in theta]


mesh_service = MeshService()
