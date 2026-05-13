"""Utilities for preparing and validating 2D PSLG boundaries."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


Point = Tuple[float, float]
ShapeComponent = Tuple[List[Point], List[List[Point]]]
EPSILON = 1e-9


def _same_point(a: Point, b: Point, tol: float = EPSILON) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _signed_area(loop: Sequence[Point]) -> float:
    area = 0.0
    n = len(loop)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % n]
        area += (x1 * y2) - (x2 * y1)
    return 0.5 * area


def _is_collinear(a: Point, b: Point, c: Point, tol: float = EPSILON) -> bool:
    return abs(_cross(a, b, c)) <= tol


def _point_on_segment(p: Point, a: Point, b: Point, tol: float = EPSILON) -> bool:
    if not _is_collinear(a, b, p, tol):
        return False
    min_x, max_x = sorted((a[0], b[0]))
    min_y, max_y = sorted((a[1], b[1]))
    return (min_x - tol <= p[0] <= max_x + tol) and (min_y - tol <= p[1] <= max_y + tol)


def _segment_intersection(
    a1: Point,
    a2: Point,
    b1: Point,
    b2: Point,
    tol: float = EPSILON,
) -> bool:
    o1 = _cross(a1, a2, b1)
    o2 = _cross(a1, a2, b2)
    o3 = _cross(b1, b2, a1)
    o4 = _cross(b1, b2, a2)

    if (o1 > tol and o2 < -tol or o1 < -tol and o2 > tol) and (
        o3 > tol and o4 < -tol or o3 < -tol and o4 > tol
    ):
        return True

    if abs(o1) <= tol and _point_on_segment(b1, a1, a2, tol):
        return True
    if abs(o2) <= tol and _point_on_segment(b2, a1, a2, tol):
        return True
    if abs(o3) <= tol and _point_on_segment(a1, b1, b2, tol):
        return True
    if abs(o4) <= tol and _point_on_segment(a2, b1, b2, tol):
        return True
    return False


def _deduplicate_loop(points: Sequence[Point], tol: float = EPSILON) -> List[Point]:
    raw = [(float(x), float(y)) for x, y in points]
    if len(raw) < 3:
        raise ValueError("A boundary loop must contain at least 3 points")

    if _same_point(raw[0], raw[-1], tol):
        raw = raw[:-1]

    cleaned: List[Point] = []
    for p in raw:
        if not cleaned or not _same_point(cleaned[-1], p, tol):
            cleaned.append(p)

    if len(cleaned) >= 2 and _same_point(cleaned[0], cleaned[-1], tol):
        cleaned.pop()

    if len(cleaned) < 3:
        raise ValueError("Boundary loop became degenerate after removing duplicate points")

    return _remove_collinear_vertices(cleaned, tol)


def _remove_collinear_vertices(loop: Sequence[Point], tol: float = EPSILON) -> List[Point]:
    if len(loop) < 3:
        return list(loop)

    work = list(loop)
    changed = True
    while changed and len(work) >= 3:
        changed = False
        for i in range(len(work)):
            prev_p = work[(i - 1) % len(work)]
            cur_p = work[i]
            next_p = work[(i + 1) % len(work)]
            if _is_collinear(prev_p, cur_p, next_p, tol):
                work.pop(i)
                changed = True
                break

    if len(work) < 3:
        raise ValueError("Boundary loop became degenerate after removing collinear points")
    return work


def point_in_loop(point: Point, loop: Sequence[Point], tol: float = EPSILON) -> bool:
    """Ray-cast point-in-polygon with boundary treated as inside."""
    x, y = point
    inside = False
    n = len(loop)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % n]

        if _point_on_segment(point, (x1, y1), (x2, y2), tol):
            return True

        intersects = ((y1 > y) != (y2 > y)) and (
            x < ((x2 - x1) * (y - y1) / ((y2 - y1) + 1e-20) + x1)
        )
        if intersects:
            inside = not inside

    return inside


def point_in_domain(
    point: Point,
    outer_loop: Sequence[Point],
    holes: Sequence[Sequence[Point]],
    tol: float = EPSILON,
) -> bool:
    if not point_in_loop(point, outer_loop, tol):
        return False
    for hole in holes:
        if point_in_loop(point, hole, tol):
            return False
    return True


def normalize_loop(
    points: Sequence[Point],
    *,
    clockwise: bool,
    tol: float = EPSILON,
) -> List[Point]:
    loop = _deduplicate_loop(points, tol)
    # Validate topology first so self-intersections report clear error messages.
    _validate_loop_simple(loop, tol)

    area = _signed_area(loop)
    if abs(area) <= tol:
        raise ValueError("Boundary loop area is too small or degenerate")

    if clockwise and area > 0:
        loop.reverse()
    if (not clockwise) and area < 0:
        loop.reverse()
    return loop


def _segments(loop: Sequence[Point]) -> List[Tuple[Point, Point]]:
    return [(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]


def _validate_loop_simple(loop: Sequence[Point], tol: float = EPSILON) -> None:
    segs = _segments(loop)
    n = len(segs)
    for i in range(n):
        a1, a2 = segs[i]
        for j in range(i + 1, n):
            if j == i:
                continue
            if j == (i + 1) % n or i == (j + 1) % n:
                continue
            b1, b2 = segs[j]
            if _segment_intersection(a1, a2, b1, b2, tol):
                raise ValueError("Invalid polygon: self-intersection detected")


def _validate_loops_intersections(
    outer: Sequence[Point],
    holes: Sequence[Sequence[Point]],
    tol: float = EPSILON,
) -> None:
    all_loops: List[Sequence[Point]] = [outer] + list(holes)
    for i, loop in enumerate(all_loops):
        _validate_loop_simple(loop, tol)
        if i > 0:
            hole_seed = loop[0]
            if not point_in_loop(hole_seed, outer, tol):
                raise ValueError("Invalid polygon: hole must be inside outer loop")

    for h_idx, hole in enumerate(holes):
        for p in hole:
            if point_in_loop(p, outer, tol):
                continue
            raise ValueError("Invalid polygon: hole vertices must be inside outer loop")

        for other_idx, other_hole in enumerate(holes):
            if other_idx <= h_idx:
                continue
            for a1, a2 in _segments(hole):
                for b1, b2 in _segments(other_hole):
                    if _segment_intersection(a1, a2, b1, b2, tol):
                        raise ValueError("Invalid polygon: holes cannot intersect each other")

    outer_segments = _segments(outer)
    for hole in holes:
        for a1, a2 in outer_segments:
            for b1, b2 in _segments(hole):
                if _segment_intersection(a1, a2, b1, b2, tol):
                    if _same_point(a1, b1, tol) or _same_point(a1, b2, tol):
                        continue
                    if _same_point(a2, b1, tol) or _same_point(a2, b2, tol):
                        continue
                    raise ValueError("Invalid polygon: outer loop intersects hole boundary")


def _quantize_key(point: Point, tol: float) -> Tuple[int, int]:
    return (int(round(point[0] / tol)), int(round(point[1] / tol)))


def build_pslg(
    outer_boundary: Sequence[Point],
    holes: Sequence[Sequence[Point]] | None = None,
    tol: float = EPSILON,
) -> dict:
    """
    Build a validated PSLG representation.

    Returns a dict containing normalized loops, vertices and segments.
    """
    hole_loops = holes or []
    outer = normalize_loop(outer_boundary, clockwise=False, tol=tol)
    normalized_holes = [normalize_loop(hole, clockwise=True, tol=tol) for hole in hole_loops]

    _validate_loops_intersections(outer, normalized_holes, tol)

    loops = [outer] + normalized_holes
    vertices: List[List[float]] = []
    vertex_lookup: dict[Tuple[int, int], int] = {}

    def register_vertex(point: Point) -> int:
        key = _quantize_key(point, tol)
        if key in vertex_lookup:
            return vertex_lookup[key]
        vertices.append([float(point[0]), float(point[1])])
        vertex_id = len(vertices)
        vertex_lookup[key] = vertex_id
        return vertex_id

    segments: List[dict] = []
    loop_info: List[dict] = []

    for loop_idx, loop in enumerate(loops):
        is_hole = loop_idx > 0
        loop_vertex_ids = [register_vertex(p) for p in loop]
        for i in range(len(loop_vertex_ids)):
            start = loop_vertex_ids[i]
            end = loop_vertex_ids[(i + 1) % len(loop_vertex_ids)]
            segments.append(
                {
                    "id": len(segments) + 1,
                    "start": start,
                    "end": end,
                    "loop_id": loop_idx,
                    "is_hole": is_hole,
                    "is_boundary": True,
                }
            )

        loop_info.append(
            {
                "loop_id": loop_idx,
                "type": "hole" if is_hole else "outer",
                "orientation": "CW" if is_hole else "CCW",
                "vertex_ids": loop_vertex_ids,
            }
        )

    return {
        "vertices": vertices,
        "segments": segments,
        "loops": loop_info,
        "outer_boundary": [[float(x), float(y)] for x, y in outer],
        "holes": [
            [[float(x), float(y)] for x, y in hole]
            for hole in normalized_holes
        ],
    }


def parse_shape_dat(shape_dat: str) -> Tuple[List[Point], List[List[Point]]]:
    """
    Parse shape.dat text content.

    Supported format:
    OUTER
    x y
    ...
    END
    HOLE
    x y
    ...
    END

    If sections are omitted, all coordinate lines are treated as OUTER.
    """
    components = parse_shape_dat_components(shape_dat)
    return components[0]


def parse_shape_dat_components(shape_dat: str) -> List[ShapeComponent]:
    """
    Parse shape.dat text into one or more polygon components.

    Multiple OUTER sections are treated as disconnected components; HOLE sections
    following an OUTER belong to that component until the next OUTER starts.
    """
    lines = []
    for raw in shape_dat.splitlines():
        stripped = raw.split("#", maxsplit=1)[0].strip()
        if stripped:
            lines.append(stripped)

    if not lines:
        raise ValueError("shape.dat content is empty")

    has_sections = any(token.upper() in {"OUTER", "HOLE", "END"} for token in lines)
    if not has_sections:
        outer = _parse_point_lines(lines)
        if len(outer) < 3:
            raise ValueError("shape.dat requires at least 3 points for OUTER boundary")
        return [(outer, [])]

    components: List[ShapeComponent] = []
    outer: List[Point] = []
    holes: List[List[Point]] = []
    current: List[Point] = []
    mode = ""

    def commit_current_section() -> None:
        nonlocal outer, holes, current, mode
        if not mode:
            return
        if mode == "OUTER":
            outer = current
        elif mode == "HOLE" and current:
            holes.append(current)
        current = []
        mode = ""

    def commit_component() -> None:
        nonlocal outer, holes
        if not outer and not holes:
            return
        if len(outer) < 3:
            raise ValueError("shape.dat OUTER section must contain at least 3 points")
        components.append((outer, holes))
        outer = []
        holes = []

    for line in lines:
        upper = line.upper()
        if upper == "OUTER":
            commit_current_section()
            commit_component()
            mode = "OUTER"
            current = []
            continue

        if upper == "HOLE":
            commit_current_section()
            if len(outer) < 3:
                raise ValueError("shape.dat HOLE section must follow a valid OUTER section")
            mode = "HOLE"
            current = []
            continue

        if upper == "END":
            commit_current_section()
            continue

        if not mode:
            raise ValueError("shape.dat coordinate lines must appear inside OUTER or HOLE sections")
        current.append(_parse_point_line(line))

    commit_current_section()
    commit_component()

    if not components:
        raise ValueError("shape.dat OUTER section must contain at least 3 points")
    return components


def _parse_point_lines(lines: Iterable[str]) -> List[Point]:
    pts: List[Point] = []
    for line in lines:
        pts.append(_parse_point_line(line))
    return pts


def _parse_point_line(line: str) -> Point:
    tokens = line.replace(",", " ").split()
    if len(tokens) != 2:
        raise ValueError(f"Invalid coordinate line in shape.dat: '{line}'")
    return float(tokens[0]), float(tokens[1])


def to_shape_dat(outer: Sequence[Point], holes: Sequence[Sequence[Point]] | None = None) -> str:
    """Serialize outer/holes loops into shape.dat text."""
    return to_shape_dat_components([(outer, holes or [])])


def to_shape_dat_components(
    components: Sequence[Tuple[Sequence[Point], Sequence[Sequence[Point]]]],
) -> str:
    """Serialize one or more outer/holes components into shape.dat text."""
    lines = ["OUTER"]
    for component_idx, (outer, holes) in enumerate(components):
        if component_idx > 0:
            lines.append("OUTER")
        for x, y in outer:
            lines.append(f"{x:.12g} {y:.12g}")
        lines.append("END")

        for hole in holes or []:
            lines.append("HOLE")
            for x, y in hole:
                lines.append(f"{x:.12g} {y:.12g}")
            lines.append("END")
    return "\n".join(lines)
