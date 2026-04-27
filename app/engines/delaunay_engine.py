import math
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from app.engines.base import MeshEngine
from app.engines.pslg import EPSILON, build_pslg, point_in_domain


Point = Tuple[float, float]


class DelaunayMeshEngine(MeshEngine):
    """Delaunay meshing engine with PSLG-aware filtering and refinement.

    Official backend implementation uses SciPy/Qhull triangulation plus
    constrained-domain filtering and refinement rules from system specs.
    """

    def generate(
        self,
        points: List[Tuple[float, float]],
        holes: Optional[List[List[Tuple[float, float]]]] = None,
        resolution: int = 10,
        **kwargs
    ) -> Tuple[List[List[float]], List[List[int]]]:
        max_area = kwargs.get("max_area")
        min_angle = kwargs.get("min_angle")
        max_edge_length = kwargs.get("max_edge_length")
        max_refine_iterations = kwargs.get("max_refine_iterations", 25)

        pslg = build_pslg(points, holes=holes or [])
        return self.generate_from_pslg(
            pslg=pslg,
            resolution=resolution,
            max_area=max_area,
            min_angle=min_angle,
            max_edge_length=max_edge_length,
            max_refine_iterations=max_refine_iterations,
        )

    def generate_from_pslg(
        self,
        pslg: dict,
        resolution: int = 10,
        max_area: Optional[float] = None,
        min_angle: Optional[float] = None,
        max_edge_length: Optional[float] = None,
        max_refine_iterations: int = 25,
        max_circumradius_ratio: float = math.sqrt(2.0),
    ) -> Tuple[List[List[float]], List[List[int]]]:
        outer = np.asarray(pslg["outer_boundary"], dtype=float)
        holes = [np.asarray(hole, dtype=float) for hole in pslg.get("holes", [])]

        span = outer.max(axis=0) - outer.min(axis=0)
        bbox_diag = float(math.hypot(float(span[0]), float(span[1])))
        target_edge = max_edge_length if max_edge_length is not None else bbox_diag / max(2 * resolution, 8)
        min_split_length = max(target_edge * 0.25, bbox_diag * 1e-4)

        boundary_points = self._sample_boundary_points(outer, holes, max_edge_length)
        interior_points = self._generate_interior_points(
            outer=outer,
            holes=holes,
            resolution=resolution,
            max_area=max_area,
            max_edge_length=max_edge_length,
        )

        if len(interior_points) > 0:
            points = np.vstack([boundary_points, interior_points])
        else:
            points = boundary_points.copy()
        merge_tol = max(EPSILON, bbox_diag * 1e-9)
        points = self._deduplicate_points(points, tol=merge_tol)

        boundary_segments = self._extract_boundary_segments(outer, holes)
        min_angle_limit = float(min_angle) if min_angle is not None else 20.7

        for _ in range(max_refine_iterations):
            if len(points) < 3:
                break

            triangulation = Delaunay(points, qhull_options="Qbb Qc Qz Q12")
            triangles = self._filter_triangles_in_domain(
                simplices=triangulation.simplices,
                points=points,
                outer=outer,
                holes=holes,
            )

            if not triangles:
                break

            bad_triangles = self._collect_bad_triangles(
                points=points,
                triangles=triangles,
                outer=outer,
                holes=holes,
                min_angle=min_angle_limit,
                max_area=max_area,
                max_edge_length=max_edge_length,
                max_ratio=max_circumradius_ratio,
            )
            if not bad_triangles:
                break

            encroached_segments: set[int] = set()
            insertion_points: List[np.ndarray] = []

            for bad in bad_triangles:
                candidate = bad["circumcenter"] if bad["use_circumcenter"] else bad["centroid"]
                enc_idx = self._find_encroached_segment(candidate, boundary_segments)
                if enc_idx is not None and self._segment_length(boundary_segments[enc_idx]) > min_split_length:
                    encroached_segments.add(enc_idx)
                else:
                    insertion_points.append(candidate)

            insertion_points = insertion_points[:200]

            made_progress = False

            if encroached_segments:
                new_segments: List[Tuple[np.ndarray, np.ndarray]] = []
                for idx, (a, b) in enumerate(boundary_segments):
                    if idx not in encroached_segments:
                        new_segments.append((a, b))
                        continue
                    midpoint = 0.5 * (a + b)
                    if np.linalg.norm(a - b) <= min_split_length:
                        new_segments.append((a, b))
                        continue
                    points = np.vstack([points, midpoint])
                    new_segments.append((a, midpoint))
                    new_segments.append((midpoint, b))
                    made_progress = True
                boundary_segments = new_segments

            if insertion_points:
                points = np.vstack([points, np.asarray(insertion_points, dtype=float)])
                made_progress = True

            points = self._deduplicate_points(points, tol=merge_tol)
            if not made_progress:
                break

        if len(points) < 3:
            return points.tolist(), []

        final_tri = Delaunay(points, qhull_options="Qbb Qc Qz Q12")
        final_elements = self._filter_triangles_in_domain(
            simplices=final_tri.simplices,
            points=points,
            outer=outer,
            holes=holes,
        )

        return points.tolist(), [[int(i) for i in tri] for tri in final_elements]

    @staticmethod
    def _segment_length(segment: Tuple[np.ndarray, np.ndarray]) -> float:
        a, b = segment
        return float(np.linalg.norm(b - a))

    @staticmethod
    def check_empty_circumcircle(
        nodes: Sequence[Sequence[float]],
        elements: Sequence[Sequence[int]],
        tolerance: float = 1e-10,
        max_triangles_to_check: int = 5000,
    ) -> bool:
        """Verify Delaunay empty circumcircle condition on triangle elements."""
        if not nodes or not elements:
            return True

        points = np.asarray(nodes, dtype=float)
        tris = np.asarray(elements, dtype=int)
        if tris.ndim != 2 or tris.shape[1] != 3:
            return True

        min_index = int(tris.min())
        if min_index == 1:
            tris = tris - 1

        if len(tris) > max_triangles_to_check:
            step = max(1, len(tris) // max_triangles_to_check)
            tris = tris[::step]

        tree = cKDTree(points)

        for tri in tris:
            tri_pts = points[tri]
            circumcenter, radius_sq = DelaunayMeshEngine._circumcircle(tri_pts)
            if not np.isfinite(circumcenter).all() or radius_sq <= tolerance:
                continue

            radius = math.sqrt(max(radius_sq - tolerance, 0.0))
            if radius <= 0.0:
                continue

            candidate_ids = tree.query_ball_point(circumcenter, radius)
            tri_set = {int(tri[0]), int(tri[1]), int(tri[2])}
            for idx in candidate_ids:
                if idx in tri_set:
                    continue
                dist_sq = float(np.sum((points[idx] - circumcenter) ** 2))
                if dist_sq < radius_sq - tolerance:
                    return False
        return True

    def _sample_boundary_points(
        self,
        outer: np.ndarray,
        holes: Sequence[np.ndarray],
        max_edge_length: Optional[float],
    ) -> np.ndarray:
        points = []
        loops = [outer] + list(holes)
        for loop in loops:
            for i in range(len(loop)):
                a = loop[i]
                b = loop[(i + 1) % len(loop)]
                points.append(a)
                if max_edge_length is None:
                    continue
                seg_len = float(np.linalg.norm(b - a))
                if seg_len <= max_edge_length + EPSILON:
                    continue
                n_split = int(math.ceil(seg_len / max_edge_length))
                for k in range(1, n_split):
                    t = k / n_split
                    points.append(a * (1.0 - t) + b * t)
        return self._deduplicate_points(np.asarray(points, dtype=float))

    def _generate_interior_points(
        self,
        outer: np.ndarray,
        holes: Sequence[np.ndarray],
        resolution: int,
        max_area: Optional[float],
        max_edge_length: Optional[float],
    ) -> np.ndarray:
        x_min, y_min = outer.min(axis=0)
        x_max, y_max = outer.max(axis=0)
        span_x = max(x_max - x_min, EPSILON)
        span_y = max(y_max - y_min, EPSILON)
        diag = math.hypot(span_x, span_y)

        spacing = diag / max(2 * resolution, 6)
        if max_area is not None:
            spacing = min(spacing, max(math.sqrt(max_area), diag / 300.0))
        if max_edge_length is not None:
            spacing = min(spacing, max_edge_length)

        spacing = max(spacing, diag / 300.0)
        nx = int(math.ceil(span_x / spacing))
        ny = int(math.ceil(span_y / spacing))
        nx = max(3, min(nx, 250))
        ny = max(3, min(ny, 250))

        xs = np.linspace(x_min, x_max, nx)
        ys = np.linspace(y_min, y_max, ny)
        xv, yv = np.meshgrid(xs, ys, indexing="xy")
        candidates = np.column_stack([xv.ravel(), yv.ravel()])

        outer_list = [tuple(p) for p in outer.tolist()]
        holes_list = [[tuple(p) for p in hole.tolist()] for hole in holes]
        boundary_segments = self._extract_boundary_segments(outer, holes)
        clearance = 0.25 * spacing

        mask = []
        for p in candidates:
            point = (float(p[0]), float(p[1]))
            if not point_in_domain(point, outer_list, holes_list):
                mask.append(False)
                continue

            if self._distance_to_boundary(np.asarray(point, dtype=float), boundary_segments) <= clearance:
                mask.append(False)
                continue
            mask.append(True)

        interior = candidates[np.asarray(mask, dtype=bool)]

        if len(interior) <= 0:
            return np.empty((0, 2), dtype=float)
        return interior

    @staticmethod
    def _distance_to_boundary(
        point: np.ndarray,
        boundary_segments: Sequence[Tuple[np.ndarray, np.ndarray]],
    ) -> float:
        min_dist = float("inf")
        for a, b in boundary_segments:
            ab = b - a
            denom = float(np.dot(ab, ab))
            if denom <= EPSILON:
                dist = float(np.linalg.norm(point - a))
            else:
                t = float(np.dot(point - a, ab) / denom)
                t = max(0.0, min(1.0, t))
                proj = a + t * ab
                dist = float(np.linalg.norm(point - proj))
            if dist < min_dist:
                min_dist = dist
        return min_dist

    def _extract_boundary_segments(
        self,
        outer: np.ndarray,
        holes: Sequence[np.ndarray],
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        segments: List[Tuple[np.ndarray, np.ndarray]] = []
        for loop in [outer] + list(holes):
            for i in range(len(loop)):
                segments.append((loop[i].copy(), loop[(i + 1) % len(loop)].copy()))
        return segments

    def _find_encroached_segment(
        self,
        point: np.ndarray,
        boundary_segments: Sequence[Tuple[np.ndarray, np.ndarray]],
    ) -> Optional[int]:
        for idx, (a, b) in enumerate(boundary_segments):
            seg_len_sq = float(np.sum((b - a) ** 2))
            if seg_len_sq <= (4.0 * EPSILON) ** 2:
                continue
            center = 0.5 * (a + b)
            radius_sq = 0.25 * seg_len_sq
            dist_sq = float(np.sum((point - center) ** 2))
            if dist_sq < radius_sq - EPSILON:
                return idx
        return None

    def _filter_triangles_in_domain(
        self,
        simplices: np.ndarray,
        points: np.ndarray,
        outer: np.ndarray,
        holes: Sequence[np.ndarray],
    ) -> List[List[int]]:
        outer_loop = [tuple(p) for p in outer.tolist()]
        holes_loops = [[tuple(p) for p in hole.tolist()] for hole in holes]

        kept: List[List[int]] = []
        for simplex in simplices:
            tri_pts = points[simplex]
            area = abs(self._cross2d(tri_pts[1] - tri_pts[0], tri_pts[2] - tri_pts[0])) * 0.5
            if area <= EPSILON:
                continue

            centroid = tri_pts.mean(axis=0)
            mid_ab = 0.5 * (tri_pts[0] + tri_pts[1])
            mid_bc = 0.5 * (tri_pts[1] + tri_pts[2])
            mid_ca = 0.5 * (tri_pts[2] + tri_pts[0])
            probes = [centroid, mid_ab, mid_bc, mid_ca]

            if all(
                point_in_domain((float(p[0]), float(p[1])), outer_loop, holes_loops)
                for p in probes
            ):
                kept.append([int(simplex[0]), int(simplex[1]), int(simplex[2])])

        return kept

    def _collect_bad_triangles(
        self,
        points: np.ndarray,
        triangles: Sequence[Sequence[int]],
        outer: np.ndarray,
        holes: Sequence[np.ndarray],
        min_angle: float,
        max_area: Optional[float],
        max_edge_length: Optional[float],
        max_ratio: float,
    ) -> List[dict]:
        outer_loop = [tuple(p) for p in outer.tolist()]
        holes_loops = [[tuple(p) for p in hole.tolist()] for hole in holes]

        bad: List[dict] = []
        for tri in triangles:
            tri_pts = points[np.asarray(tri, dtype=int)]
            edge_lengths = self._edge_lengths(tri_pts)
            shortest = max(min(edge_lengths), EPSILON)
            longest = max(edge_lengths)

            angles = self._triangle_angles_deg(tri_pts)
            min_ang = min(angles)

            circumcenter, radius_sq = self._circumcircle(tri_pts)
            circumradius = math.sqrt(radius_sq) if radius_sq > EPSILON else float("inf")
            ratio = circumradius / shortest if shortest > EPSILON else float("inf")

            area = abs(self._cross2d(tri_pts[1] - tri_pts[0], tri_pts[2] - tri_pts[0])) * 0.5
            violated = (
                (min_ang < min_angle - 1e-9)
                or (ratio > max_ratio + 1e-9)
                or (max_area is not None and area > max_area + 1e-12)
                or (max_edge_length is not None and longest > max_edge_length + 1e-9)
            )
            if not violated:
                continue

            centroid = tri_pts.mean(axis=0)
            use_circumcenter = (
                np.isfinite(circumcenter).all()
                and point_in_domain(
                    (float(circumcenter[0]), float(circumcenter[1])),
                    outer_loop,
                    holes_loops,
                )
            )

            severity = max(min_angle - min_ang, 0.0)
            severity += max(ratio - max_ratio, 0.0)
            if max_area is not None:
                severity += max(area - max_area, 0.0)
            if max_edge_length is not None:
                severity += max(longest - max_edge_length, 0.0)

            bad.append(
                {
                    "triangle": tri,
                    "severity": severity,
                    "min_angle": min_ang,
                    "ratio": ratio,
                    "area": area,
                    "circumcenter": circumcenter,
                    "centroid": centroid,
                    "use_circumcenter": use_circumcenter,
                }
            )

        bad.sort(key=lambda item: item["severity"], reverse=True)
        return bad[:200]

    @staticmethod
    def _edge_lengths(tri_pts: np.ndarray) -> List[float]:
        return [
            float(np.linalg.norm(tri_pts[1] - tri_pts[0])),
            float(np.linalg.norm(tri_pts[2] - tri_pts[1])),
            float(np.linalg.norm(tri_pts[0] - tri_pts[2])),
        ]

    @staticmethod
    def _triangle_angles_deg(tri_pts: np.ndarray) -> List[float]:
        def angle(u: np.ndarray, v: np.ndarray) -> float:
            nu = float(np.linalg.norm(u))
            nv = float(np.linalg.norm(v))
            if nu <= EPSILON or nv <= EPSILON:
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
        if abs(d) <= EPSILON:
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
    def _deduplicate_points(points: np.ndarray, tol: float = EPSILON) -> np.ndarray:
        if len(points) == 0:
            return np.empty((0, 2), dtype=float)

        unique: List[np.ndarray] = []
        seen: set[Tuple[int, int]] = set()
        for p in points:
            key = (int(round(float(p[0]) / tol)), int(round(float(p[1]) / tol)))
            if key in seen:
                continue
            seen.add(key)
            unique.append(np.asarray(p, dtype=float))
        return np.asarray(unique, dtype=float)

    @staticmethod
    def _cross2d(u: np.ndarray, v: np.ndarray) -> float:
        return float(u[0] * v[1] - u[1] * v[0])


