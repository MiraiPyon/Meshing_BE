"""
Boolean Geometry Engine — CSG operations on 2D polygons using Shapely.

Supports:
  - union:     A ∪ B
  - subtract:  A − B  (difference)
  - intersect: A ∩ B
"""

from typing import List, Tuple
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.validation import make_valid


BooleanOp = str  # "union" | "subtract" | "intersect"


def _coords_to_polygon(coords: List[List[float]]) -> Polygon:
    """Convert [[x, y], ...] → Shapely Polygon, ensuring validity."""
    poly = Polygon([(c[0], c[1]) for c in coords])
    if not poly.is_valid:
        poly = make_valid(poly)
    return poly


def _polygon_to_coords(poly: Polygon) -> Tuple[
    List[List[float]],          # outer boundary
    List[List[List[float]]],    # holes
]:
    """Convert Shapely Polygon → ([[x,y], ...], [[[x,y],...], ...])."""
    exterior = [[float(x), float(y)] for x, y in poly.exterior.coords[:-1]]
    holes = []
    for interior in poly.interiors:
        hole = [[float(x), float(y)] for x, y in interior.coords[:-1]]
        holes.append(hole)
    return exterior, holes


def boolean_operation(
    polygon_a: List[List[float]],
    polygon_b: List[List[float]],
    operation: BooleanOp,
) -> dict:
    """
    Perform a boolean operation on two 2D polygons.

    Args:
        polygon_a: Outer boundary of shape A as [[x,y], ...]
        polygon_b: Outer boundary of shape B as [[x,y], ...]
        operation: "union", "subtract", or "intersect"

    Returns:
        {
            "outer_boundary": [[x,y], ...],
            "holes": [[[x,y], ...], ...],
            "area": float,
            "num_vertices": int,
            "is_valid": bool,
        }

    Raises:
        ValueError: if operation fails or results in empty geometry
    """
    a = _coords_to_polygon(polygon_a)
    b = _coords_to_polygon(polygon_b)

    if operation == "union":
        result = a.union(b)
    elif operation == "subtract":
        result = a.difference(b)
    elif operation == "intersect":
        result = a.intersection(b)
    else:
        raise ValueError(f"Unknown operation: {operation}. Use: union, subtract, intersect")

    if result.is_empty:
        raise ValueError(f"Boolean {operation} resulted in empty geometry")

    polygons: List[Polygon] = []
    if isinstance(result, Polygon):
        polygons = [result]
    elif isinstance(result, MultiPolygon):
        polygons = list(result.geoms)
    elif isinstance(result, GeometryCollection):
        polygons = [geom for geom in result.geoms if isinstance(geom, Polygon)]

    if not polygons:
        raise ValueError(
            f"Boolean {operation} produced unsupported geometry type: {type(result).__name__}"
        )

    polygons.sort(key=lambda poly: float(poly.area), reverse=True)
    components = []
    total_area = 0.0
    for poly in polygons:
        outer, holes = _polygon_to_coords(poly)
        area = float(poly.area)
        total_area += area
        components.append(
            {
                "outer_boundary": outer,
                "holes": holes,
                "area": area,
                "num_vertices": len(outer),
                "is_valid": poly.is_valid,
            }
        )

    primary = components[0]

    return {
        # Backward-compatible fields (primary/largest component)
        "outer_boundary": primary["outer_boundary"],
        "holes": primary["holes"],
        "area": primary["area"],
        "num_vertices": primary["num_vertices"],
        "is_valid": all(component["is_valid"] for component in components),
        # New explicit multi-component contract
        "components": components,
        "component_count": len(components),
        "total_area": total_area,
        "is_multipolygon": len(components) > 1,
    }
