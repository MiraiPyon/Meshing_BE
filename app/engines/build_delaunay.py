"""Native divide-and-conquer Delaunay triangulation.

This module owns the backend BuildDelaunay path required by the release
specification. It uses a quad-edge topology, lower common tangent merge, and
InCircle predicates instead of delegating triangulation to SciPy/Qhull. Highly
degenerate point sets are guarded by a deterministic native cavity fallback so
structured grids still satisfy the empty circumcircle check.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np


EPSILON = 1e-12
Triangle = Tuple[int, int, int]


@dataclass(frozen=True)
class _Circle:
    center_x: float
    center_y: float
    radius_sq: float


class _QuadEdge:
    """Single directed edge in Guibas-Stolfi quad-edge topology."""

    _next_id = 0

    def __init__(self) -> None:
        self.id = _QuadEdge._next_id
        _QuadEdge._next_id += 1
        self.rot: Optional[_QuadEdge] = None
        self.next: Optional[_QuadEdge] = None
        self.origin: Optional[int] = None
        self.deleted = False

    @property
    def sym(self) -> _QuadEdge:
        return self.rot.rot  # type: ignore[union-attr,return-value]

    @property
    def invrot(self) -> _QuadEdge:
        return self.rot.rot.rot  # type: ignore[union-attr,return-value]

    @property
    def dest(self) -> Optional[int]:
        return self.sym.origin

    @dest.setter
    def dest(self, value: int) -> None:
        self.sym.origin = value

    @property
    def onext(self) -> _QuadEdge:
        return self.next  # type: ignore[return-value]

    @property
    def oprev(self) -> _QuadEdge:
        return self.rot.next.rot  # type: ignore[union-attr,return-value]

    @property
    def lnext(self) -> _QuadEdge:
        return self.invrot.onext.rot  # type: ignore[return-value]

    @property
    def rprev(self) -> _QuadEdge:
        return self.sym.onext


class BuildDelaunay:
    """Native BuildDelaunay using divide-and-conquer quad-edge merge."""

    @staticmethod
    def triangulate(points: Sequence[Sequence[float]]) -> List[List[int]]:
        pts = np.asarray(points, dtype=float)
        if len(pts) < 3:
            return []

        working, original_indices = BuildDelaunay._deduplicate_with_indices(pts)
        if len(working) < 3 or BuildDelaunay._all_collinear(working):
            return []

        order = sorted(range(len(working)), key=lambda idx: (working[idx][0], working[idx][1], idx))
        _QuadEdge._next_id = 0
        edges: List[_QuadEdge] = []
        BuildDelaunay._divide_and_conquer(working, order, edges)

        result: set[Triangle] = set()
        for tri in BuildDelaunay._collect_triangles(edges, working):
            mapped = tuple(original_indices[vertex] for vertex in tri)
            oriented = BuildDelaunay._orient_triangle(mapped, pts)
            if abs(BuildDelaunay._orientation(pts[oriented[0]], pts[oriented[1]], pts[oriented[2]])) <= EPSILON:
                continue
            result.add(oriented)

        triangles = [list(tri) for tri in sorted(result)]
        if BuildDelaunay.validate_empty_circumcircle(pts, triangles):
            return triangles

        # The quad-edge merge is sensitive to cocircular/collinear degeneracy.
        # Keep the production path native by falling back to deterministic
        # InCircle cavity insertion instead of SciPy/Qhull.
        return BuildDelaunay._triangulate_incremental(
            working=working,
            original_points=pts,
            original_indices=original_indices,
        )

    @staticmethod
    def incircle(a: Sequence[float], b: Sequence[float], c: Sequence[float], d: Sequence[float]) -> float:
        """Positive when d is inside the circumcircle of CCW triangle abc."""
        ax, ay = float(a[0]) - float(d[0]), float(a[1]) - float(d[1])
        bx, by = float(b[0]) - float(d[0]), float(b[1]) - float(d[1])
        cx, cy = float(c[0]) - float(d[0]), float(c[1]) - float(d[1])

        det = (
            (ax * ax + ay * ay) * (bx * cy - by * cx)
            - (bx * bx + by * by) * (ax * cy - ay * cx)
            + (cx * cx + cy * cy) * (ax * by - ay * bx)
        )
        orientation = BuildDelaunay._orientation(a, b, c)
        return det if orientation >= 0 else -det

    @staticmethod
    def validate_empty_circumcircle(
        points: Sequence[Sequence[float]],
        triangles: Sequence[Sequence[int]],
        tolerance: float = 1e-10,
    ) -> bool:
        pts = np.asarray(points, dtype=float)
        for tri in triangles:
            a, b, c = [int(v) for v in tri]
            circle = BuildDelaunay._circumcircle(pts[a], pts[b], pts[c])
            if not math.isfinite(circle.radius_sq) or circle.radius_sq <= tolerance:
                continue
            tri_set = {a, b, c}
            for idx, point in enumerate(pts):
                if idx in tri_set:
                    continue
                dist_sq = float((point[0] - circle.center_x) ** 2 + (point[1] - circle.center_y) ** 2)
                if dist_sq < circle.radius_sq - tolerance:
                    return False
        return True

    @staticmethod
    def _divide_and_conquer(
        points: np.ndarray,
        indices: Sequence[int],
        edges: List[_QuadEdge],
    ) -> Tuple[_QuadEdge, _QuadEdge]:
        n = len(indices)
        if n == 2:
            edge = BuildDelaunay._make_edge(indices[0], indices[1], edges)
            return edge, edge.sym

        if n == 3:
            a = BuildDelaunay._make_edge(indices[0], indices[1], edges)
            b = BuildDelaunay._make_edge(indices[1], indices[2], edges)
            BuildDelaunay._splice(a.sym, b)

            orientation = BuildDelaunay._orientation(points[indices[0]], points[indices[1]], points[indices[2]])
            if orientation > EPSILON:
                BuildDelaunay._connect(b, a, edges)
                return a, b.sym
            if orientation < -EPSILON:
                c = BuildDelaunay._connect(b, a, edges)
                return c.sym, c
            return a, b.sym

        midpoint = n // 2
        left_outer, left_inner = BuildDelaunay._divide_and_conquer(points, indices[:midpoint], edges)
        right_inner, right_outer = BuildDelaunay._divide_and_conquer(points, indices[midpoint:], edges)

        left_inner, right_inner = BuildDelaunay._lower_common_tangent(points, left_inner, right_inner)
        base = BuildDelaunay._connect(right_inner.sym, left_inner, edges)

        if left_inner.origin == left_outer.origin:
            left_outer = base.sym
        if right_inner.origin == right_outer.origin:
            right_outer = base

        while True:
            left_candidate = base.sym.onext
            if BuildDelaunay._valid_candidate(points, left_candidate, base):
                while BuildDelaunay._edge_incircle(points, base, left_candidate, left_candidate.onext) > EPSILON:
                    next_candidate = left_candidate.onext
                    BuildDelaunay._delete_edge(left_candidate)
                    left_candidate = next_candidate

            right_candidate = base.oprev
            if BuildDelaunay._valid_candidate(points, right_candidate, base):
                while BuildDelaunay._edge_incircle(points, base, right_candidate, right_candidate.oprev) > EPSILON:
                    next_candidate = right_candidate.oprev
                    BuildDelaunay._delete_edge(right_candidate)
                    right_candidate = next_candidate

            left_valid = BuildDelaunay._valid_candidate(points, left_candidate, base)
            right_valid = BuildDelaunay._valid_candidate(points, right_candidate, base)
            if not left_valid and not right_valid:
                break

            if not left_valid or (
                right_valid
                and BuildDelaunay._incircle_by_index(
                    points,
                    left_candidate.dest,
                    left_candidate.origin,
                    right_candidate.origin,
                    right_candidate.dest,
                )
                > EPSILON
            ):
                base = BuildDelaunay._connect(right_candidate, base.sym, edges)
            else:
                base = BuildDelaunay._connect(base.sym, left_candidate.sym, edges)

        return left_outer, right_outer

    @staticmethod
    def _lower_common_tangent(
        points: np.ndarray,
        left_inner: _QuadEdge,
        right_inner: _QuadEdge,
    ) -> Tuple[_QuadEdge, _QuadEdge]:
        while True:
            if BuildDelaunay._left_of(points, right_inner.origin, left_inner):
                left_inner = left_inner.lnext
            elif BuildDelaunay._right_of(points, left_inner.origin, right_inner):
                right_inner = right_inner.rprev
            else:
                return left_inner, right_inner

    @staticmethod
    def _make_edge(origin: int, dest: int, edges: List[_QuadEdge]) -> _QuadEdge:
        e0 = _QuadEdge()
        e1 = _QuadEdge()
        e2 = _QuadEdge()
        e3 = _QuadEdge()

        e0.rot = e1
        e1.rot = e2
        e2.rot = e3
        e3.rot = e0

        e0.next = e0
        e1.next = e3
        e2.next = e2
        e3.next = e1

        e0.origin = origin
        e0.dest = dest
        edges.extend([e0, e1, e2, e3])
        return e0

    @staticmethod
    def _splice(a: _QuadEdge, b: _QuadEdge) -> None:
        alpha = a.onext.rot
        beta = b.onext.rot

        a_next = a.onext
        b_next = b.onext
        alpha_next = alpha.onext
        beta_next = beta.onext

        a.next = b_next
        b.next = a_next
        alpha.next = beta_next
        beta.next = alpha_next

    @staticmethod
    def _connect(a: _QuadEdge, b: _QuadEdge, edges: List[_QuadEdge]) -> _QuadEdge:
        if a.dest is None or b.origin is None:
            raise ValueError("Cannot connect incomplete quad-edge records")

        edge = BuildDelaunay._make_edge(a.dest, b.origin, edges)
        BuildDelaunay._splice(edge, a.lnext)
        BuildDelaunay._splice(edge.sym, b)
        return edge

    @staticmethod
    def _delete_edge(edge: _QuadEdge) -> None:
        BuildDelaunay._splice(edge, edge.oprev)
        BuildDelaunay._splice(edge.sym, edge.sym.oprev)
        edge.deleted = True
        edge.sym.deleted = True
        edge.rot.deleted = True  # type: ignore[union-attr]
        edge.invrot.deleted = True

    @staticmethod
    def _collect_triangles(edges: Iterable[_QuadEdge], points: np.ndarray) -> List[Triangle]:
        result: set[Triangle] = set()
        for edge in edges:
            if edge.deleted or edge.origin is None or edge.dest is None:
                continue
            try:
                a = edge.origin
                b = edge.dest
                c = edge.lnext.dest
                closes = edge.lnext.lnext.lnext is edge
            except AttributeError:
                continue
            if c is None or not closes or len({a, b, c}) < 3:
                continue
            if BuildDelaunay._orientation(points[a], points[b], points[c]) <= EPSILON:
                continue
            result.add(tuple(sorted((a, b, c))))

        oriented: List[Triangle] = []
        for tri in sorted(result):
            oriented.append(BuildDelaunay._orient_triangle(tri, points))
        return oriented

    @staticmethod
    def _triangulate_incremental(
        working: np.ndarray,
        original_points: np.ndarray,
        original_indices: Sequence[int],
    ) -> List[List[int]]:
        order = sorted(range(len(working)), key=lambda idx: (working[idx][0], working[idx][1], idx))
        sorted_points = working[order]
        sorted_to_original = [original_indices[order_idx] for order_idx in order]

        super_points = BuildDelaunay._super_triangle(sorted_points)
        all_points = np.vstack([sorted_points, super_points])
        n = len(sorted_points)

        triangles: List[Triangle] = [
            BuildDelaunay._orient_triangle((n, n + 1, n + 2), all_points)
        ]

        for point_idx in range(n):
            triangles = BuildDelaunay._insert_point(all_points, triangles, point_idx)

        result: set[Triangle] = set()
        for tri in triangles:
            if any(vertex >= n for vertex in tri):
                continue
            mapped = tuple(sorted_to_original[vertex] for vertex in tri)
            oriented = BuildDelaunay._orient_triangle(mapped, original_points)
            if abs(
                BuildDelaunay._orientation(
                    original_points[oriented[0]],
                    original_points[oriented[1]],
                    original_points[oriented[2]],
                )
            ) <= EPSILON:
                continue
            result.add(oriented)

        return [list(tri) for tri in sorted(result)]

    @staticmethod
    def _insert_point(points: np.ndarray, triangles: List[Triangle], point_idx: int) -> List[Triangle]:
        point = points[point_idx]
        bad: List[Triangle] = []

        for tri in triangles:
            a, b, c = tri
            if BuildDelaunay.incircle(points[a], points[b], points[c], point) > EPSILON:
                bad.append(tri)

        if not bad:
            return triangles

        bad_set = set(bad)
        edge_count: dict[Tuple[int, int], int] = {}
        directed_edges: dict[Tuple[int, int], Tuple[int, int]] = {}

        for a, b, c in bad:
            for edge in ((a, b), (b, c), (c, a)):
                key = tuple(sorted(edge))
                edge_count[key] = edge_count.get(key, 0) + 1
                directed_edges[key] = edge

        boundary_edges = [
            directed_edges[key]
            for key, count in edge_count.items()
            if count == 1
        ]

        next_triangles = [tri for tri in triangles if tri not in bad_set]
        for a, b in boundary_edges:
            tri = BuildDelaunay._orient_triangle((a, b, point_idx), points)
            if abs(BuildDelaunay._orientation(points[tri[0]], points[tri[1]], points[tri[2]])) > EPSILON:
                next_triangles.append(tri)

        return BuildDelaunay._deduplicate_triangles(next_triangles)

    @staticmethod
    def _deduplicate_triangles(triangles: Iterable[Triangle]) -> List[Triangle]:
        seen: set[Tuple[int, int, int]] = set()
        result: List[Triangle] = []
        for tri in triangles:
            key = tuple(sorted(tri))
            if key in seen:
                continue
            seen.add(key)
            result.append(tri)
        return result

    @staticmethod
    def _super_triangle(points: np.ndarray) -> np.ndarray:
        min_x = float(np.min(points[:, 0]))
        min_y = float(np.min(points[:, 1]))
        max_x = float(np.max(points[:, 0]))
        max_y = float(np.max(points[:, 1]))
        dx = max(max_x - min_x, EPSILON)
        dy = max(max_y - min_y, EPSILON)
        delta = max(dx, dy)
        mid_x = 0.5 * (min_x + max_x)
        mid_y = 0.5 * (min_y + max_y)
        scale = 64.0 * delta
        return np.asarray(
            [
                [mid_x - 2.0 * scale, mid_y - scale],
                [mid_x, mid_y + 2.0 * scale],
                [mid_x + 2.0 * scale, mid_y - scale],
            ],
            dtype=float,
        )

    @staticmethod
    def _valid_candidate(points: np.ndarray, edge: _QuadEdge, base: _QuadEdge) -> bool:
        if edge.deleted or edge.dest is None:
            return False
        return BuildDelaunay._right_of(points, edge.dest, base)

    @staticmethod
    def _edge_incircle(points: np.ndarray, base: _QuadEdge, candidate: _QuadEdge, next_candidate: _QuadEdge) -> float:
        if (
            base.dest is None
            or base.origin is None
            or candidate.dest is None
            or next_candidate.dest is None
        ):
            return -float("inf")
        return BuildDelaunay._incircle_by_index(
            points,
            base.dest,
            base.origin,
            candidate.dest,
            next_candidate.dest,
        )

    @staticmethod
    def _incircle_by_index(
        points: np.ndarray,
        a: Optional[int],
        b: Optional[int],
        c: Optional[int],
        d: Optional[int],
    ) -> float:
        if a is None or b is None or c is None or d is None:
            return -float("inf")
        return BuildDelaunay.incircle(points[a], points[b], points[c], points[d])

    @staticmethod
    def _left_of(points: np.ndarray, idx: Optional[int], edge: _QuadEdge) -> bool:
        if idx is None or edge.origin is None or edge.dest is None:
            return False
        return BuildDelaunay._orientation(points[idx], points[edge.origin], points[edge.dest]) > EPSILON

    @staticmethod
    def _right_of(points: np.ndarray, idx: Optional[int], edge: _QuadEdge) -> bool:
        if idx is None or edge.origin is None or edge.dest is None:
            return False
        return BuildDelaunay._orientation(points[idx], points[edge.dest], points[edge.origin]) > EPSILON

    @staticmethod
    def _deduplicate_with_indices(points: np.ndarray) -> Tuple[np.ndarray, List[int]]:
        unique: List[np.ndarray] = []
        original_indices: List[int] = []
        seen: set[Tuple[float, float]] = set()
        for idx, point in enumerate(points):
            key = (round(float(point[0]), 12), round(float(point[1]), 12))
            if key in seen:
                continue
            seen.add(key)
            unique.append(np.asarray(point, dtype=float))
            original_indices.append(idx)
        return np.asarray(unique, dtype=float), original_indices

    @staticmethod
    def _orient_triangle(tri: Triangle, points: np.ndarray) -> Triangle:
        a, b, c = tri
        if BuildDelaunay._orientation(points[a], points[b], points[c]) < 0:
            return (a, c, b)
        return tri

    @staticmethod
    def _all_collinear(points: np.ndarray) -> bool:
        for a, b, c in combinations(points, 3):
            if abs(BuildDelaunay._orientation(a, b, c)) > EPSILON:
                return False
        return True

    @staticmethod
    def _orientation(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
        return (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (
            float(b[1]) - float(a[1])
        ) * (float(c[0]) - float(a[0]))

    @staticmethod
    def _circumcircle(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> _Circle:
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        cx, cy = float(c[0]), float(c[1])

        d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) <= EPSILON:
            return _Circle(float("inf"), float("inf"), float("inf"))

        ax2_ay2 = ax * ax + ay * ay
        bx2_by2 = bx * bx + by * by
        cx2_cy2 = cx * cx + cy * cy
        ux = (ax2_ay2 * (by - cy) + bx2_by2 * (cy - ay) + cx2_cy2 * (ay - by)) / d
        uy = (ax2_ay2 * (cx - bx) + bx2_by2 * (ax - cx) + cx2_cy2 * (bx - ax)) / d
        radius_sq = (ux - ax) ** 2 + (uy - ay) ** 2
        return _Circle(float(ux), float(uy), float(radius_sq))
