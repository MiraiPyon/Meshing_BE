import numpy as np
from typing import Tuple, List, Optional
from app.engines.base import MeshEngine


class QuadMeshEngine(MeshEngine):
    """
    Engine tạo lưới tứ giác có cấu trúc (structured grid).
    Chỉ hỗ trợ hình chữ nhật.
    """

    def generate(
        self,
        points: List[Tuple[float, float]],
        holes: Optional[List[List[Tuple[float, float]]]] = None,
        resolution: int = 10,
        **kwargs
    ) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Generate quad mesh cho rectangle.

        Args:
            points: Boundary points (tự động trích xuất bounding box)
            holes: Quad mesh không hỗ trợ holes, sẽ bị bỏ qua.
            resolution: Số phần tử mặc định theo mỗi chiều.
            **kwargs: nx, ny để chỉ định trực tiếp số phần tử.

        Returns:
            nodes: List of [x, y] coordinates
            elements: List of [n1, n2, n3, n4] node indices (1-based, CCW)
        """
        if holes:
            raise ValueError("Quad mesh does not support holes")
        if not self._is_axis_aligned_rectangle(points):
            raise ValueError("Quad mesh only supports axis-aligned rectangular boundaries")

        x_min = min(p[0] for p in points)
        y_min = min(p[1] for p in points)
        x_max = max(p[0] for p in points)
        y_max = max(p[1] for p in points)

        nx = kwargs.get("nx", resolution)
        ny = kwargs.get("ny", resolution)

        # Tạo node coordinates
        x = np.linspace(x_min, x_max, nx + 1)
        y = np.linspace(y_min, y_max, ny + 1)

        # Tạo mesh grid
        xv, yv = np.meshgrid(x, y, indexing='ij')

        # Flatten to get node coordinates
        nodes = np.column_stack([xv.flatten(), yv.flatten()])

        # Create elements (quads)
        elements = []
        for i in range(nx):
            for j in range(ny):
                # Node indices (1-based), CCW order
                # Bottom-left: (i, j)
                n1 = i * (ny + 1) + j + 1
                # Bottom-right: (i+1, j)
                n2 = (i + 1) * (ny + 1) + j + 1
                # Top-right: (i+1, j+1)
                n3 = (i + 1) * (ny + 1) + j + 2
                # Top-left: (i, j+1)
                n4 = i * (ny + 1) + j + 2

                elements.append([n1, n2, n3, n4])

        return nodes.tolist(), elements

    @staticmethod
    def _is_axis_aligned_rectangle(points: List[Tuple[float, float]], tol: float = 1e-9) -> bool:
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
