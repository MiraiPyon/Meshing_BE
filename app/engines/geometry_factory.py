import json
from uuid import UUID
from app.database.models import Geometry as GeometryModel
from app.database.models import GeometryType as GeometryTypeEnum
from app.schemas.request import RectangleCreate, CircleCreate, PolygonCreate
from app.engines.pslg import build_pslg


class GeometryFactory:
    """Factory Pattern: Khởi tạo linh hoạt các Primitives và Polygon."""

    @staticmethod
    def create_geometry(data, user_id: UUID) -> GeometryModel:
        if isinstance(data, RectangleCreate):
            return GeometryFactory._create_rectangle(data, user_id)
        if isinstance(data, CircleCreate):
            return GeometryFactory._create_circle(data, user_id)
        if isinstance(data, PolygonCreate):
            return GeometryFactory._create_polygon(data, user_id)
        raise ValueError("Unsupported geometry creation request.")

    @staticmethod
    def _create_rectangle(data: RectangleCreate, user_id: UUID) -> GeometryModel:
        x_max = data.x_min + data.width
        y_max = data.y_min + data.height
        return GeometryModel(
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

    @staticmethod
    def _create_circle(data: CircleCreate, user_id: UUID) -> GeometryModel:
        return GeometryModel(
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

    @staticmethod
    def _create_polygon(data: PolygonCreate, user_id: UUID) -> GeometryModel:
        pslg = build_pslg(outer_boundary=[tuple(p) for p in data.points], holes=[])
        outer = pslg["outer_boundary"]
        x_coords = [p[0] for p in outer]
        y_coords = [p[1] for p in outer]

        return GeometryModel(
            user_id=user_id,
            name=data.name,
            geometry_type=GeometryTypeEnum.POLYGON,
            points=json.dumps(outer),
            closed=1 if data.closed else 0,
            bound_x_min=min(x_coords),
            bound_x_max=max(x_coords),
            bound_y_min=min(y_coords),
            bound_y_max=max(y_coords),
        )
