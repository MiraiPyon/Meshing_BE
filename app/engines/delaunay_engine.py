import numpy as np
from scipy.spatial import Delaunay
from typing import Tuple, List, Optional
from app.engines.base import MeshEngine


def _convert_to_int_list(item):
    """Recursively convert numpy ints to Python ints."""
    if hasattr(item, '__iter__') and not isinstance(item, (str, bytes)):
        return [_convert_to_int_list(x) for x in item]
    return int(item)


class DelaunayMeshEngine(MeshEngine):
    """
    Engine tạo lưới tam giác sử dụng thuật toán Delaunay.
    Hỗ trợ polygon bất kỳ.
    """

    def generate(
        self,
        points: List[Tuple[float, float]],
        resolution: int = 10,
        max_area: Optional[float] = None,
        min_angle: Optional[float] = None,
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate triangular mesh sử dụng Delaunay triangulation.

        Args:
            points: Boundary points as (x, y) tuples
            resolution: Hint cho số điểm trên boundary
            max_area: Diện tích tối đa mỗi tam giác
            min_angle: Góc tối thiểu (độ)

        Returns:
            nodes: List of [x, y] coordinates
            elements: List of [n1, n2, n3] node indices (1-based)
        """
        # Thêm điểm bên trong nếu cần
        points_array = np.array(points)

        # Tính bounds
        x_min, y_min = points_array.min(axis=0)
        x_max, y_max = points_array.max(axis=0)

        # Tạo interior points nếu là polygon đơn giản
        interior_points = self._generate_interior_points(
            points_array, resolution, max_area
        )

        # Kết hợp boundary và interior points
        if len(interior_points) > 0:
            all_points = np.vstack([points_array, interior_points])
        else:
            all_points = points_array

        # Delaunay triangulation
        tri = Delaunay(all_points)

        # Lọc các tam giác nằm trong polygon
        elements = self._filter_triangles_in_polygon(
            tri, all_points, points_array
        )

        elements_1based = [[int(x) for x in _convert_to_int_list(elem)] for elem in elements]

        return all_points.tolist(), elements_1based

    def _generate_interior_points(
        self,
        boundary: np.ndarray,
        resolution: int,
        max_area: Optional[float] = None,
    ) -> np.ndarray:
        """Tạo các điểm bên trong polygon"""
        x_min, y_min = boundary.min(axis=0)
        x_max, y_max = boundary.max(axis=0)

        # Số điểm theo mỗi chiều
        n_points = max(resolution // 2, 3)

        # Tạo grid
        x = np.linspace(x_min, x_max, n_points)
        y = np.linspace(y_min, y_max, n_points)

        xv, yv = np.meshgrid(x[1:-1], y[1:-1], indexing='ij')
        interior = np.column_stack([xv.flatten(), yv.flatten()])

        # Lọc điểm nằm trong polygon
        from matplotlib.path import Path

        boundary_path = Path(boundary)
        mask = boundary_path.contains_points(interior)

        return interior[mask]

    def _filter_triangles_in_polygon(
        self,
        tri: Delaunay,
        points: np.ndarray,
        boundary: np.ndarray,
    ) -> List[List[int]]:
        """Lọc các tam giác nằm hoàn toàn trong polygon"""
        from matplotlib.path import Path

        boundary_path = Path(boundary)
        elements = []

        for simplex in tri.simplices:
            # Lấy tọa độ các đỉnh tam giác
            triangle_points = points[simplex]

            # Kiểm tra tâm tam giác có nằm trong polygon không
            centroid = triangle_points.mean(axis=0)

            if boundary_path.contains_point(centroid):
                elements.append(simplex.tolist())

        return elements


class DelaunayMeshEngineWithHoles(DelaunayMeshEngine):
    """
    Delaunay engine hỗ trợ holes (vùng trống bên trong).
    """

    def generate_with_holes(
        self,
        outer_boundary: List[Tuple[float, float]],
        holes: List[List[Tuple[float, float]]],
        resolution: int = 10,
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate mesh với holes.

        Args:
            outer_boundary: Điểm boundary ngoài
            holes: Danh sách các holes (mỗi hole là list các điểm)
            resolution: Resolution hint

        Returns:
            nodes, elements
        """
        # Kết hợp outer boundary và inner boundaries (holes)
        all_boundaries = [outer_boundary] + holes

        # Tạo mesh
        points_array = np.array(outer_boundary)

        # Thêm điểm bên trong
        interior_points = self._generate_interior_points_with_holes(
            points_array, holes, resolution
        )

        # Kết hợp tất cả điểm
        all_points = np.vstack([points_array, interior_points])

        # Delaunay
        tri = Delaunay(all_points)

        # Lọc tam giác
        from matplotlib.path import Path

        outer_path = Path(outer_boundary)
        hole_paths = [Path(hole) for hole in holes]

        elements = []
        for simplex in tri.simplices:
            centroid = all_points[simplex].mean(axis=0)

            # Phải nằm trong outer và ngoài tất cả holes
            if outer_path.contains_point(centroid):
                in_hole = any(path.contains_point(centroid) for path in hole_paths)
                if not in_hole:
                    elements.append(simplex.tolist())

        elements_1based = [[int(x) for x in _convert_to_int_list(elem)] for elem in elements]
        return all_points.tolist(), elements_1based

    def _generate_interior_points_with_holes(
        self,
        outer_boundary: np.ndarray,
        holes: List[List[Tuple[float, float]]],
        resolution: int,
    ) -> np.ndarray:
        """Tạo điểm bên trong, trừ các vùng holes"""
        from matplotlib.path import Path

        x_min, y_min = outer_boundary.min(axis=0)
        x_max, y_max = outer_boundary.max(axis=0)

        n_points = max(resolution // 2, 3)
        x = np.linspace(x_min, x_max, n_points)
        y = np.linspace(y_min, y_max, n_points)

        xv, yv = np.meshgrid(x[1:-1], y[1:-1], indexing='ij')
        interior = np.column_stack([xv.flatten(), yv.flatten()])

        outer_path = Path(outer_boundary)
        hole_paths = [Path(hole) for hole in holes]

        mask = outer_path.contains_points(interior)
        for hole_path in hole_paths:
            mask &= ~hole_path.contains_points(interior)

        return interior[mask]
