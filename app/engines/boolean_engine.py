"""
Boolean Geometry Engine — CSG operations on 2D polygons using Shapely.

Supports:
  - union:     A ∪ B
  - subtract:  A − B  (difference)
  - intersect: A ∩ B
"""

from typing import List, Tuple
from shapely.geometry import Polygon, MultiPolygon
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

    # Handle MultiPolygon — take the largest polygon
    if isinstance(result, MultiPolygon):
        result = max(result.geoms, key=lambda g: g.area)

    if not isinstance(result, Polygon):
        raise ValueError(
            f"Boolean {operation} produced unsupported geometry type: {type(result).__name__}"
        )

    outer, holes = _polygon_to_coords(result)

    return {
        "outer_boundary": outer,
        "holes": holes,
        "area": float(result.area),
        "num_vertices": len(outer),
        "is_valid": result.is_valid,
    }
