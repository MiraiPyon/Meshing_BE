"""
Mesh Service — CRUD cho Geometry và Mesh, mỗi user chỉ thấy data của mình.
"""

import io
import json
import math
import zipfile
from typing import Any, List, Optional, Sequence, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.schemas.request import (
    RectangleCreate,
    CircleCreate,
    TriangleCreate,
    PolygonCreate,
    QuadMeshCreate,
    DelaunayMeshCreate,
    MeshFromSketchCreate,
    ShapeDatMeshCreate,
)
from app.schemas.response import GeometryResponse, MeshResponse, Bounds
from app.engines.delaunay_engine import DelaunayMeshEngine
from app.engines.factory import MeshEngineFactory
from app.engines.pslg import build_pslg, parse_shape_dat, to_shape_dat
from app.database.models import Geometry as GeometryModel
from app.database.models import Mesh as MeshModel
from app.database.models import GeometryType as GeometryTypeEnum
from app.database.models import MeshType as MeshTypeEnum
from app.engines.geometry_factory import GeometryFactory
from app.services.events import mesh_events



class MeshService:
    """Service xử lý Geometry và Mesh — mỗi user chỉ truy cập data của mình."""

    def __init__(self):
        # We don't pre-instantiate engines, we will use the Factory dynamically
        pass

    # ============== Geometry Methods ==============

    def create_rectangle(self, db: Session, data: RectangleCreate, user_id: UUID) -> GeometryResponse:
        geometry = GeometryFactory.create_geometry(data, user_id)

        db.add(geometry)
        db.commit()
        db.refresh(geometry)
        return self._geometry_to_response(geometry)

    def create_circle(self, db: Session, data: CircleCreate, user_id: UUID) -> GeometryResponse:
        geometry = GeometryFactory.create_geometry(data, user_id)

        db.add(geometry)
        db.commit()
        db.refresh(geometry)
        return self._geometry_to_response(geometry)

    def create_triangle(self, db: Session, data: TriangleCreate, user_id: UUID) -> GeometryResponse:
        geometry = GeometryFactory.create_geometry(data, user_id)

        db.add(geometry)
        db.commit()
        db.refresh(geometry)
        return self._geometry_to_response(geometry)

    def create_polygon(self, db: Session, data: PolygonCreate, user_id: UUID) -> GeometryResponse:
        geometry = GeometryFactory.create_geometry(data, user_id)

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

        engine = MeshEngineFactory.create("quad")
        outer = [
            (float(x_min), float(y_min)),
            (float(x_max), float(y_min)),
            (float(x_max), float(y_max)),
            (float(x_min), float(y_max)),
        ]
        nodes, elements = engine.generate(
            points=outer,
            holes=[],
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
            meshing_params=json.dumps(
                {
                    "strategy": "quad",
                    "element_type": "Q4",
                    "nx": data.nx,
                    "ny": data.ny,
                }
            ),
        )

        db.add(mesh)
        db.commit()
        db.refresh(mesh)

        # Publish Mesh Created Event
        mesh_events.notify_sync("mesh_created", {"mesh_id": str(mesh.id), "name": mesh.name, "type": "quad"})

        return self._mesh_to_response(db, mesh)

    def create_delaunay_mesh(self, db: Session, data: DelaunayMeshCreate, user_id: UUID) -> MeshResponse:
        geometry = db.query(GeometryModel).filter(
            GeometryModel.id == data.geometry_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not geometry:
            raise ValueError(f"Geometry {data.geometry_id} not found")

        pslg = self._geometry_to_pslg(geometry)
        if not pslg:
            raise ValueError("Unable to derive PSLG from geometry")

        outer = [tuple(p) for p in pslg["outer_boundary"]]
        holes = [[tuple(p) for p in loop] for loop in pslg.get("holes", [])]

        engine = MeshEngineFactory.create("delaunay")
        nodes, elements = engine.generate(
            points=outer,
            holes=holes,
            resolution=20,
            max_area=data.max_area,
            min_angle=data.min_angle,
            max_edge_length=data.max_edge_length,
            max_circumradius_ratio=data.max_circumradius_ratio,
        )

        mesh = MeshModel(
            geometry_id=data.geometry_id,
            mesh_type=MeshTypeEnum.DELAUNAY,
            name=f"{geometry.name}_delaunay",
            node_count=len(nodes),
            element_count=len(elements),
            nodes=json.dumps(nodes),
            elements=json.dumps(elements),
            meshing_params=json.dumps(
                {
                    "strategy": "delaunay",
                    "element_type": "T3",
                    "max_area": data.max_area,
                    "min_angle": data.min_angle,
                    "max_edge_length": data.max_edge_length,
                    "max_circumradius_ratio": data.max_circumradius_ratio,
                }
            ),
        )

        db.add(mesh)
        db.commit()
        db.refresh(mesh)

        # Publish Mesh Created Event
        mesh_events.notify_sync("mesh_created", {"mesh_id": str(mesh.id), "name": mesh.name, "type": "delaunay"})

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
        """One-shot: lưu geometry + tạo mesh từ sketch (outer + holes)."""
        return self._create_mesh_from_loops(
            db=db,
            user_id=user_id,
            name=data.name,
            outer=[tuple(p) for p in data.outer_boundary],
            holes=[[tuple(p) for p in loop] for loop in data.holes],
            element_type=data.element_type,
            max_area=data.max_area,
            min_angle=data.min_angle,
            max_edge_length=data.max_edge_length,
            max_circumradius_ratio=data.max_circumradius_ratio,
            nx=data.nx,
            ny=data.ny,
        )

    def create_mesh_from_shape_dat(
        self,
        db: Session,
        data: ShapeDatMeshCreate,
        user_id: UUID,
    ) -> MeshResponse:
        """Generate mesh from shape.dat text content."""
        outer, holes = parse_shape_dat(data.shape_dat)
        return self._create_mesh_from_loops(
            db=db,
            user_id=user_id,
            name=data.name,
            outer=outer,
            holes=holes,
            element_type="delaunay",
            max_area=data.max_area,
            min_angle=data.min_angle,
            max_edge_length=data.max_edge_length,
            max_circumradius_ratio=data.max_circumradius_ratio,
            nx=10,
            ny=10,
        )

    def export_mesh(self, db: Session, mesh_id: UUID, user_id: UUID, fmt: str) -> dict:
        """Export mesh sang json/dat/csv/csv_zip."""
        mesh = db.query(MeshModel).join(GeometryModel).filter(
            MeshModel.id == mesh_id,
            GeometryModel.user_id == user_id,
        ).first()
        if not mesh:
            raise ValueError(f"Mesh {mesh_id} not found")

        geometry = db.query(GeometryModel).filter(GeometryModel.id == mesh.geometry_id).first()

        nodes = json.loads(mesh.nodes)
        elements = json.loads(mesh.elements)
        analysis = self._build_mesh_analysis(nodes, elements, mesh.mesh_type)
        elements_one_based = self._normalize_elements_to_one_based(elements, len(nodes))

        if fmt == "json":
            return {
                "format": "json",
                "content_type": "application/json",
                "filename": f"{mesh.name}.json",
                "data": {
                    "nodes": nodes,
                    "elements": elements,
                    "node_count": mesh.node_count,
                    "element_count": mesh.element_count,
                    "element_type": analysis["element_type"],
                    "dof_total": analysis["dof_total"],
                    "dashboard": analysis["dashboard"],
                    "connectivity_matrices": analysis["connectivity_matrices"],
                    "meshing_params": (
                        json.loads(mesh.meshing_params)
                        if mesh.meshing_params else None
                    ),
                },
            }

        if fmt == "dat":
            lines = [f"# Mesh: {mesh.name}",
                     f"# Nodes: {mesh.node_count}  Elements: {mesh.element_count}",
                     "NODES", f"{mesh.node_count}"]
            for i, (x, y) in enumerate(nodes, 1):
                lines.append(f"{i:6d}  {x:14.8f}  {y:14.8f}")
            lines.append("ELEMENTS")
            lines.append(f"{mesh.element_count}")
            for i, elem in enumerate(elements_one_based, 1):
                node_str = "  ".join(f"{n:6d}" for n in elem)
                lines.append(f"{i:6d}  {node_str}")
            return {
                "format": "dat",
                "content_type": "text/plain",
                "filename": f"{mesh.name}.dat",
                "data": "\n".join(lines),
            }

        if fmt == "csv":
            max_nodes_per_element = max((len(elem) for elem in elements_one_based), default=0)
            headers = ["section", "id", "x", "y"] + [
                f"n{idx + 1}" for idx in range(max_nodes_per_element)
            ]
            lines = [",".join(headers)]
            for i, (x, y) in enumerate(nodes, 1):
                lines.append(",".join(["node", str(i), str(x), str(y)] + [""] * max_nodes_per_element))
            for i, elem in enumerate(elements_one_based, 1):
                padded = [str(n) for n in elem] + [""] * (max_nodes_per_element - len(elem))
                lines.append(",".join(["element", str(i), "", ""] + padded))
            return {
                "format": "csv",
                "content_type": "text/csv",
                "filename": f"{mesh.name}.csv",
                "data": "\n".join(lines),
            }

        if fmt == "csv_zip":
            node_lines = ["id,x,y"]
            for i, (x, y) in enumerate(nodes, 1):
                node_lines.append(f"{i},{x},{y}")

            elem_lines = [
                "id," + ",".join(f"n{j+1}" for j in range(len(elements_one_based[0])))
                if elements_one_based
                else "id"
            ]
            for i, elem in enumerate(elements_one_based, 1):
                elem_lines.append(f"{i}," + ",".join(str(n) for n in elem))

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("nodes.csv", "\n".join(node_lines))
                archive.writestr("elements.csv", "\n".join(elem_lines))

            return {
                "format": "csv_zip",
                "content_type": "application/zip",
                "filename": f"{mesh.name}_csv.zip",
                "data": buffer.getvalue(),
            }

        if fmt == "shape":
            pslg = self._geometry_to_pslg(geometry)
            if not pslg:
                raise ValueError("shape export is only available for geometry-backed polygonal meshes")
            shape_txt = to_shape_dat(
                outer=[tuple(p) for p in pslg["outer_boundary"]],
                holes=[[tuple(p) for p in h] for h in pslg.get("holes", [])],
            )
            return {
                "format": "shape",
                "content_type": "text/plain",
                "filename": f"{mesh.name}.shape.dat",
                "data": shape_txt,
            }

        raise ValueError(f"Unknown format: {fmt}. Supported: json, dat, csv, csv_zip, shape")

    # ============== Helper Methods ==============

    def _geometry_to_response(self, geometry: GeometryModel) -> GeometryResponse:
        bounds = Bounds(
            x_min=geometry.bound_x_min, x_max=geometry.bound_x_max,
            y_min=geometry.bound_y_min, y_max=geometry.bound_y_max,
        )
        points_payload = json.loads(geometry.points) if geometry.points else None
        if isinstance(points_payload, dict):
            points = points_payload.get("outer")
        else:
            points = points_payload
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

        nodes = json.loads(mesh.nodes)
        elements = json.loads(mesh.elements)
        analysis = self._build_mesh_analysis(nodes, elements, mesh.mesh_type)
        pslg = self._geometry_to_pslg(geometry)

        return MeshResponse(
            id=mesh.id, geometry_id=mesh.geometry_id,
            mesh_type=mesh.mesh_type, name=mesh.name,
            node_count=mesh.node_count, element_count=mesh.element_count,
            nodes=nodes, elements=elements,
            element_type=analysis["element_type"],
            dof_total=analysis["dof_total"],
            dashboard=analysis["dashboard"],
            pslg=pslg,
            connectivity_matrices=analysis["connectivity_matrices"],
            meshing_params=json.loads(mesh.meshing_params) if mesh.meshing_params else None,
            bounds=bounds, created_at=mesh.created_at,
        )

    def _create_mesh_from_loops(
        self,
        db: Session,
        user_id: UUID,
        name: str,
        outer: Sequence[Tuple[float, float]],
        holes: Sequence[Sequence[Tuple[float, float]]],
        element_type: str,
        max_area: Optional[float],
        min_angle: Optional[float],
        max_edge_length: Optional[float],
        max_circumradius_ratio: Optional[float],
        nx: int,
        ny: int,
    ) -> MeshResponse:
        pslg = build_pslg(outer_boundary=outer, holes=holes)
        outer_norm = [tuple(p) for p in pslg["outer_boundary"]]
        holes_norm = [[tuple(p) for p in loop] for loop in pslg.get("holes", [])]
        strategy = element_type.strip().lower()

        if strategy == "quad":
            if holes_norm:
                raise ValueError("Quad mesh from sketch only supports a single outer rectangle (no holes)")
            if not self._is_axis_aligned_rectangle(outer_norm):
                raise ValueError("Quad mesh from sketch requires an axis-aligned rectangular outer boundary")

        xs = [p[0] for p in outer_norm]
        ys = [p[1] for p in outer_norm]

        geometry = GeometryModel(
            user_id=user_id,
            name=name,
            geometry_type=GeometryTypeEnum.POLYGON,
            points=json.dumps({"outer": pslg["outer_boundary"], "holes": pslg["holes"]}),
            closed=1,
            bound_x_min=min(xs),
            bound_x_max=max(xs),
            bound_y_min=min(ys),
            bound_y_max=max(ys),
        )
        db.add(geometry)
        db.commit()
        db.refresh(geometry)

        engine = MeshEngineFactory.create(strategy)

        nodes, elements = engine.generate(
            points=outer_norm,
            holes=holes_norm,
            resolution=20,
            max_area=max_area,
            min_angle=min_angle,
            max_edge_length=max_edge_length,
            max_circumradius_ratio=max_circumradius_ratio,
            nx=nx,
            ny=ny,
        )

        if strategy == "quad":
            mesh_type = MeshTypeEnum.QUAD
            mesh_name = f"{name}_quad_{nx}x{ny}"
        else:
            mesh_type = MeshTypeEnum.DELAUNAY
            mesh_name = f"{name}_delaunay"

        mesh = MeshModel(
            geometry_id=geometry.id,
            mesh_type=mesh_type,
            name=mesh_name,
            node_count=len(nodes),
            element_count=len(elements),
            nodes=json.dumps(nodes),
            elements=json.dumps(elements),
            meshing_params=json.dumps(
                {
                    "strategy": strategy,
                    "element_type": "Q4" if strategy == "quad" else "T3",
                    "nx": nx if strategy == "quad" else None,
                    "ny": ny if strategy == "quad" else None,
                    "max_area": max_area if strategy != "quad" else None,
                    "min_angle": min_angle if strategy != "quad" else None,
                    "max_edge_length": max_edge_length if strategy != "quad" else None,
                    "max_circumradius_ratio": max_circumradius_ratio if strategy != "quad" else None,
                    "outer_vertices": len(outer_norm),
                    "hole_count": len(holes_norm),
                }
            ),
        )
        db.add(mesh)
        db.commit()
        db.refresh(mesh)

        # Publish Mesh Created Event
        mesh_events.notify_sync("mesh_created", {"mesh_id": str(mesh.id), "name": mesh.name, "type": strategy})

        return self._mesh_to_response(db, mesh)

    @staticmethod
    def _is_axis_aligned_rectangle(points: Sequence[Tuple[float, float]], tol: float = 1e-9) -> bool:
        if len(points) != 4:
            return False

        xs = sorted({round(float(p[0]) / tol) for p in points})
        ys = sorted({round(float(p[1]) / tol) for p in points})
        if len(xs) != 2 or len(ys) != 2:
            return False

        x_values = sorted({float(p[0]) for p in points})
        y_values = sorted({float(p[1]) for p in points})
        if len(x_values) != 2 or len(y_values) != 2:
            return False

        expected = {
            (x_values[0], y_values[0]),
            (x_values[0], y_values[1]),
            (x_values[1], y_values[0]),
            (x_values[1], y_values[1]),
        }
        actual = {(float(p[0]), float(p[1])) for p in points}
        return actual == expected

    def _geometry_to_pslg(self, geometry: Optional[GeometryModel]) -> Optional[dict]:
        if geometry is None:
            return None

        if geometry.geometry_type == GeometryTypeEnum.RECTANGLE:
            outer = [
                (float(geometry.x_min), float(geometry.y_min)),
                (float(geometry.x_min + geometry.width), float(geometry.y_min)),
                (float(geometry.x_min + geometry.width), float(geometry.y_min + geometry.height)),
                (float(geometry.x_min), float(geometry.y_min + geometry.height)),
            ]
            return build_pslg(outer_boundary=outer, holes=[])

        if geometry.geometry_type == GeometryTypeEnum.CIRCLE:
            outer = self._generate_circle_boundary(
                float(geometry.center_x),
                float(geometry.center_y),
                float(geometry.radius),
                resolution=64,
            )
            return build_pslg(outer_boundary=outer, holes=[])

        if geometry.geometry_type in {GeometryTypeEnum.TRIANGLE, GeometryTypeEnum.POLYGON}:
            payload = json.loads(geometry.points) if geometry.points else []
            if isinstance(payload, dict):
                outer = [tuple(p) for p in payload.get("outer", [])]
                holes = [[tuple(p) for p in loop] for loop in payload.get("holes", [])]
            else:
                outer = [tuple(p) for p in payload]
                holes = []
            if len(outer) < 3:
                return None
            return build_pslg(outer_boundary=outer, holes=holes)

        return None

    def _build_mesh_analysis(
        self,
        nodes: Sequence[Sequence[float]],
        elements: Sequence[Sequence[int]],
        mesh_type: MeshTypeEnum,
    ) -> dict:
        node_count = len(nodes)
        if node_count == 0:
            return {
                "element_type": None,
                "dof_total": 0,
                "dashboard": {
                    "dof_per_node": 2,
                    "dof_total": 0,
                    "element_type": None,
                    "element_size_distribution": [],
                    "mesh_quality": {},
                    "empty_circumcircle": True,
                },
                "connectivity_matrices": {
                    "nodes_matrix": [],
                    "edges_matrix": [],
                    "tris_matrix": [],
                },
            }

        nodes_arr = np.asarray(nodes, dtype=float)
        elements_one_based = self._normalize_elements_to_one_based(elements, node_count)
        elements_zero_based = [[idx - 1 for idx in elem] for elem in elements_one_based]

        element_vertex_count = len(elements_one_based[0]) if elements_one_based else 0
        element_type = "T3" if element_vertex_count == 3 else "Q4" if element_vertex_count == 4 else None

        element_areas = self._compute_element_areas(nodes_arr, elements_zero_based)
        area_histogram = self._histogram(element_areas, bin_count=10)

        triangles = self._triangles_for_quality(elements_zero_based)
        quality = self._compute_quality_metrics(nodes_arr, triangles)

        empty_circumcircle = None
        if mesh_type == MeshTypeEnum.DELAUNAY and element_type == "T3":
            empty_circumcircle = DelaunayMeshEngine.check_empty_circumcircle(
                nodes=nodes,
                elements=elements_one_based,
                tolerance=1e-10,
            )

        connectivity = self._build_connectivity_matrices(nodes_arr, triangles)
        dof_total = node_count * 2

        dashboard = {
            "dof_per_node": 2,
            "dof_total": dof_total,
            "element_type": element_type,
            "element_size_distribution": area_histogram,
            "mesh_quality": quality,
            "empty_circumcircle": empty_circumcircle,
        }

        return {
            "element_type": element_type,
            "dof_total": dof_total,
            "dashboard": dashboard,
            "connectivity_matrices": connectivity,
        }

    @staticmethod
    def _normalize_elements_to_one_based(
        elements: Sequence[Sequence[int]],
        node_count: int,
    ) -> List[List[int]]:
        if not elements:
            return []

        casted = [[int(v) for v in elem] for elem in elements]
        flat = [idx for elem in casted for idx in elem]
        min_idx = min(flat)
        max_idx = max(flat)

        if min_idx == 0 and max_idx <= node_count - 1:
            return [[idx + 1 for idx in elem] for elem in casted]
        if min_idx >= 1 and max_idx <= node_count:
            return casted
        raise ValueError("Element indexing is invalid for the provided node list")

    @staticmethod
    def _compute_element_areas(
        nodes: np.ndarray,
        elements_zero_based: Sequence[Sequence[int]],
    ) -> List[float]:
        areas: List[float] = []
        for elem in elements_zero_based:
            pts = nodes[np.asarray(elem, dtype=int)]
            if len(elem) == 3:
                area = abs(MeshService._cross2d(pts[1] - pts[0], pts[2] - pts[0])) * 0.5
            elif len(elem) == 4:
                x = pts[:, 0]
                y = pts[:, 1]
                area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
            else:
                continue
            areas.append(float(area))
        return areas

    @staticmethod
    def _histogram(values: Sequence[float], bin_count: int) -> List[dict]:
        if not values:
            return []

        arr = np.asarray(values, dtype=float)
        if np.allclose(arr, arr[0]):
            left = float(arr[0])
            right = float(arr[0])
            return [{"left": left, "right": right, "count": int(len(arr))}]

        hist, edges = np.histogram(arr, bins=min(bin_count, max(1, len(arr))))
        bins = []
        for i in range(len(hist)):
            bins.append(
                {
                    "left": float(edges[i]),
                    "right": float(edges[i + 1]),
                    "count": int(hist[i]),
                }
            )
        return bins

    @staticmethod
    def _triangles_for_quality(elements_zero_based: Sequence[Sequence[int]]) -> List[List[int]]:
        triangles: List[List[int]] = []
        for elem in elements_zero_based:
            if len(elem) == 3:
                triangles.append([int(elem[0]), int(elem[1]), int(elem[2])])
            elif len(elem) == 4:
                triangles.append([int(elem[0]), int(elem[1]), int(elem[2])])
                triangles.append([int(elem[0]), int(elem[2]), int(elem[3])])
        return triangles

    def _compute_quality_metrics(self, nodes: np.ndarray, triangles: Sequence[Sequence[int]]) -> dict:
        if not triangles:
            return {
                "min_angle_deg": None,
                "max_angle_deg": None,
                "avg_angle_deg": None,
                "min_circumradius_edge_ratio": None,
                "max_circumradius_edge_ratio": None,
                "avg_circumradius_edge_ratio": None,
                "skinny_triangle_count": 0,
                "bad_ratio_count": 0,
                "passes_min_angle": True,
                "passes_circumradius_edge_ratio": True,
                "circumradius_edge_ratio_histogram": [],
            }

        min_angles: List[float] = []
        ratios: List[float] = []

        for tri in triangles:
            tri_pts = nodes[np.asarray(tri, dtype=int)]
            edges = [
                float(np.linalg.norm(tri_pts[1] - tri_pts[0])),
                float(np.linalg.norm(tri_pts[2] - tri_pts[1])),
                float(np.linalg.norm(tri_pts[0] - tri_pts[2])),
            ]
            shortest = max(min(edges), 1e-14)

            angles = self._triangle_angles_deg(tri_pts)
            min_angle = min(angles)
            min_angles.append(min_angle)

            circumcenter, radius_sq = self._circumcircle(tri_pts)
            if not np.isfinite(circumcenter).all() or radius_sq <= 1e-14:
                ratio = float("inf")
            else:
                ratio = math.sqrt(radius_sq) / shortest
            ratios.append(float(ratio))

        ratio_hist = self._histogram([r for r in ratios if np.isfinite(r)], bin_count=10)
        skinny_count = sum(1 for a in min_angles if a < 20.7)
        bad_ratio_count = sum(1 for r in ratios if r > math.sqrt(2.0))

        return {
            "min_angle_deg": float(min(min_angles)),
            "max_angle_deg": float(max(min_angles)),
            "avg_angle_deg": float(np.mean(min_angles)),
            "min_circumradius_edge_ratio": float(np.nanmin(ratios)),
            "max_circumradius_edge_ratio": float(np.nanmax(ratios)),
            "avg_circumradius_edge_ratio": float(np.nanmean(ratios)),
            "skinny_triangle_count": int(skinny_count),
            "bad_ratio_count": int(bad_ratio_count),
            "passes_min_angle": skinny_count == 0,
            "passes_circumradius_edge_ratio": bad_ratio_count == 0,
            "circumradius_edge_ratio_histogram": ratio_hist,
        }

    @staticmethod
    def _triangle_angles_deg(tri_pts: np.ndarray) -> List[float]:
        def angle(u: np.ndarray, v: np.ndarray) -> float:
            nu = float(np.linalg.norm(u))
            nv = float(np.linalg.norm(v))
            if nu <= 1e-14 or nv <= 1e-14:
                return 0.0
            c = float(np.dot(u, v) / (nu * nv))
            c = max(-1.0, min(1.0, c))
            return math.degrees(math.acos(c))

        a, b, c = tri_pts
        return [
            angle(b - a, c - a),
            angle(a - b, c - b),
            angle(a - c, b - c),
        ]

    @staticmethod
    def _circumcircle(tri_pts: np.ndarray) -> Tuple[np.ndarray, float]:
        ax, ay = tri_pts[0]
        bx, by = tri_pts[1]
        cx, cy = tri_pts[2]

        d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) <= 1e-14:
            return np.array([np.inf, np.inf], dtype=float), float("inf")

        ax2_ay2 = ax * ax + ay * ay
        bx2_by2 = bx * bx + by * by
        cx2_cy2 = cx * cx + cy * cy
        ux = (ax2_ay2 * (by - cy) + bx2_by2 * (cy - ay) + cx2_cy2 * (ay - by)) / d
        uy = (ax2_ay2 * (cx - bx) + bx2_by2 * (ax - cx) + cx2_cy2 * (bx - ax)) / d
        center = np.array([ux, uy], dtype=float)
        radius_sq = float(np.sum((center - tri_pts[0]) ** 2))
        return center, radius_sq

    @staticmethod
    def _cross2d(u: np.ndarray, v: np.ndarray) -> float:
        return float(u[0] * v[1] - u[1] * v[0])

    @staticmethod
    def _build_connectivity_matrices(nodes: np.ndarray, triangles: Sequence[Sequence[int]]) -> dict:
        edge_map: dict[Tuple[int, int], int] = {}
        edge_to_adjacent_tris: dict[int, List[int]] = {}
        tris_matrix: List[List[int]] = []

        for tri_id, tri in enumerate(triangles, start=1):
            n1, n2, n3 = [int(idx) + 1 for idx in tri]
            tri_edges = [(n1, n2), (n2, n3), (n3, n1)]
            edge_ids: List[int] = []

            for a, b in tri_edges:
                key = (min(a, b), max(a, b))
                edge_id = edge_map.get(key)
                if edge_id is None:
                    edge_id = len(edge_map) + 1
                    edge_map[key] = edge_id
                    edge_to_adjacent_tris[edge_id] = []
                edge_to_adjacent_tris[edge_id].append(tri_id)
                edge_ids.append(edge_id)

            tris_matrix.append([tri_id, n1, n2, n3, edge_ids[0], edge_ids[1], edge_ids[2]])

        node_to_edges: dict[int, List[int]] = {idx + 1: [] for idx in range(len(nodes))}
        edges_matrix: List[List[Any]] = []

        for (n_start, n_end), edge_id in sorted(edge_map.items(), key=lambda item: item[1]):
            tri_refs = edge_to_adjacent_tris[edge_id]
            tri_left = tri_refs[0] if tri_refs else 0
            tri_right = tri_refs[1] if len(tri_refs) > 1 else 0
            is_boundary = 1 if len(tri_refs) == 1 else 0
            is_internal = 1 if len(tri_refs) > 1 else 0

            p1 = nodes[n_start - 1]
            p2 = nodes[n_end - 1]
            length = float(np.linalg.norm(p2 - p1))
            midpoint_x = float(0.5 * (p1[0] + p2[0]))
            midpoint_y = float(0.5 * (p1[1] + p2[1]))

            edges_matrix.append(
                [
                    edge_id,
                    n_start,
                    n_end,
                    is_boundary,
                    is_internal,
                    tri_left,
                    tri_right,
                    length,
                    midpoint_x,
                    midpoint_y,
                ]
            )

            node_to_edges[n_start].append(edge_id)
            node_to_edges[n_end].append(edge_id)

        nodes_matrix: List[List[Any]] = []
        for node_id in range(1, len(nodes) + 1):
            x, y = nodes[node_id - 1]
            nodes_matrix.append([node_id, float(x), float(y), sorted(node_to_edges[node_id])])

        return {
            "nodes_matrix": nodes_matrix,
            "edges_matrix": edges_matrix,
            "tris_matrix": tris_matrix,
        }

    @staticmethod
    def _generate_circle_boundary(
        cx: float, cy: float, radius: float, resolution: int = 32,
    ) -> List[Tuple[float, float]]:
        theta = np.linspace(0, 2 * np.pi, resolution, endpoint=False)
        return [(cx + radius * np.cos(t), cy + radius * np.sin(t)) for t in theta]


mesh_service = MeshService()
